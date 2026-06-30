"""
Test Case Generation Service - 批量生成Mixin
包含批量生成测试用例的流式输出逻辑

类型覆盖补全（_enhance_coverage_for_point）拆分至 _coverage_enhancement_mixin；
模块历史失败归因（_preload_module_failure_feedback / _refine_context_for_point）
拆分至 _module_failure_feedback_mixin。本模块保留主流程 generate_test_cases_batch。
"""
import asyncio
import copy
from typing import List, Dict, Any, Optional, AsyncGenerator

from loguru import logger

from app.services.test_case_generation.base_mixin import ContentSanitizer
from app.services.test_case_generation._coverage_enhancement_mixin import (
    BatchCoverageEnhancementMixin,
)
from app.services.test_case_generation._module_failure_feedback_mixin import (
    BatchModuleFailureFeedbackMixin,
)


class TestCaseGenerationBatchMixin(
    BatchCoverageEnhancementMixin,
    BatchModuleFailureFeedbackMixin,
):
    """测试用例生成服务 - 批量生成Mixin

    聚合类型覆盖补全子 Mixin 与模块历史失败归因子 Mixin，本类保留
    AI 并发控制与 generate_test_cases_batch 主流程。
    """

    _DEFAULT_AI_CONCURRENCY = 3

    def _get_ai_generation_concurrency(self) -> int:
        from app.core.config import settings
        value = int(getattr(settings, "AI_CASE_GENERATION_CONCURRENCY", self._DEFAULT_AI_CONCURRENCY))
        return max(1, value)

    async def generate_test_cases_batch(
        self,
        project_id: int,
        user_id: int,
        test_point_ids: Optional[List[int]] = None,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_page: int = 1,
        test_point_page_size: int = 100,
        case_type: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        批量生成测试用例

        Args:
            project_id: 项目ID
            user_id: 用户ID
            test_point_ids: 测试点ID列表
            requirement_file_ids: 需求文档文件ID列表
            ui_file_ids: UI原型图文件ID列表
            test_point_page: 测试点页码
            test_point_page_size: 测试点每页数量
            case_type: 用例类型（可选，不指定时由AI智能判断）

        Yields:
            生成进度和结果
        """
        # 先获取上下文，提取context_stats和warnings用于首帧推送
        context = await self.get_context_for_generation(
            project_id=project_id,
            user_id=user_id,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_ids=test_point_ids,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size
        )

        if hasattr(self, 'enrich_context_with_trust_and_scoring'):
            self.enrich_context_with_trust_and_scoring(context, project_id)

        context_stats = context.get("context_stats", {})
        warnings = context.get("warnings", [])
        evidence_refs = context.get("evidence_refs", {})

        yield {"progress": 5, "message": "获取上下文信息", "status": "running", "context_stats": context_stats, "warnings": warnings, "evidence_refs": evidence_refs}

        if warnings:
            for warning in warnings[:3]:
                if isinstance(warning, dict):
                    msg_text = str(warning.get("message", ""))
                    warning_detail = warning
                else:
                    msg_text = str(warning)
                    warning_detail = {"message": str(warning), "code": "UNKNOWN"}
                yield {"progress": 5, "message": msg_text, "status": "warning", "warning_detail": warning_detail}

        test_points = context.get("test_points", [])
        total = len(test_points)

        if total == 0:
            yield {"progress": 100, "message": "没有找到测试点", "status": "warning", "data": []}
            return

        pagination = context.get("pagination", {})

        yield {
            "progress": 10,
            "message": f"开始生成{total}个测试用例",
            "status": "running",
            "total": total,
            "pagination": pagination
        }

        created_cases = []
        failed_count = 0

        primary_requirement_file_id = requirement_file_ids[0] if requirement_file_ids else None
        concurrency = self._get_ai_generation_concurrency()
        semaphore = asyncio.Semaphore(concurrency)

        # R4 修复：批量预加载各模块历史失败归因，消除 _refine_context_for_point 的 N+1 查询。
        # 在并发生成循环外一次性查完全部 module，缓存传入 _generate_one 供每个测试点复用。
        module_failures = self._preload_module_failure_feedback(project_id, test_points)

        async def _generate_one(index: int, point: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    # 并发安全：按测试点深拷贝 base_context，避免 asyncio.Semaphore 控制的
                    # 3 路并发生成共享嵌套可变对象（ui_specs、evidence_refs、warnings、
                    # context_stats、history_cases）导致一个测试点的修改污染其他测试点。
                    # context 仅含可序列化的 dict/list/str/int/float，无 DB session 或
                    # ORM 对象，可安全深拷贝。
                    point_context = copy.deepcopy(context)
                    # Task 12: 注入历史执行失败归因（await 确保 DB 查询实际执行）
                    # R4: 传入预加载缓存，避免每个测试点独立查询同模块数据
                    await self._refine_context_for_point(
                        point_context, point, project_id, module_failures=module_failures
                    )
                    generated = await self.generate_test_case_for_point(
                        context=point_context,
                        test_point=point,
                        project_id=project_id,
                        case_type=case_type
                    )
                    return {
                        "index": index,
                        "test_point": point,
                        "generated_case": generated,
                        "point_context": point_context,
                        "error": None,
                    }
                except Exception as e:
                    logger.error(f"生成测试用例失败: {e}")
                    return {
                        "index": index,
                        "test_point": point,
                        "generated_case": None,
                        "error": e,
                    }

        yield {
            "progress": 10,
            "message": f"AI并发生成已启动，并发数{concurrency}",
            "status": "running",
            "total": total,
            "concurrency": concurrency,
        }

        generation_tasks = [
            asyncio.create_task(_generate_one(i, test_point))
            for i, test_point in enumerate(test_points)
        ]

        for completed, task in enumerate(asyncio.as_completed(generation_tasks), 1):
            result = await task
            i = result["index"]
            test_point = result["test_point"]
            generated_case = result["generated_case"]
            if result["error"] is not None or generated_case is None:
                failed_count += 1
                yield {
                    "progress": int(10 + completed / total * 85),
                    "message": f"生成第{i + 1}个用例失败",
                    "status": "running",
                    "error": True,
                    "failed_count": failed_count,
                    "current": completed,
                    "total": total,
                }
                continue

            try:
                candidate_cases = [generated_case]
                candidate_cases.extend(generated_case.get("_extra_cases", []))
                # 类型覆盖补全：检测 positive/boundary/negative 缺失并补充生成，
                # 复用 _generate_one 已深拷贝的 point_context 保证并发安全
                # 成功路径 result["point_context"] 必然存在（_generate_one 成功分支已写入），
                # 不再回退到共享 context，避免 deepcopy 契约被绕过导致并发污染
                candidate_cases = await self._enhance_coverage_for_point(
                    candidate_cases,
                    test_point,
                    result["point_context"],
                )
                saved_cases_for_point = []
                skipped_count = 0

                for candidate_case in candidate_cases:
                    try:
                        saved_case = await self._save_test_case(
                            project_id=project_id,
                            generated_case=candidate_case,
                            test_point=test_point,
                            requirement_file_id=primary_requirement_file_id
                        )
                        created_cases.append(saved_case)
                        saved_cases_for_point.append(saved_case)
                    except Exception as save_e:
                        skipped_count += 1
                        failed_count += 1
                        logger.warning(f"case skipped by generation quality gate: {save_e}")

                progress = int(10 + completed / total * 85)
                case_payload = None
                if saved_cases_for_point:
                    first_saved = saved_cases_for_point[0]
                    case_payload = {
                        "id": first_saved.id,
                        "title": ContentSanitizer.sanitize_for_log(first_saved.title),
                        "module": first_saved.module
                    }
                yield {
                    "progress": progress,
                    "message": f"已生成{i + 1}/{total}个测试用例",
                    "status": "running",
                    "current": completed,
                    "total": total,
                    "case": case_payload,
                    "saved_count": len(saved_cases_for_point),
                    "skipped_count": skipped_count
                }

            except Exception as e:
                failed_count += 1
                logger.error(f"生成测试用例失败: {e}")
                yield {
                    "progress": int(10 + (i + 1) / total * 85),
                    "message": f"生成第{i + 1}个用例失败",
                    "status": "running",
                    "error": True,
                    "failed_count": failed_count
                }

        yield {
            "progress": 100,
            "message": f"完成！成功{len(created_cases)}个，失败{failed_count}个",
            "status": "success" if failed_count == 0 else "partial",
            "total": total,
            "created": len(created_cases),
            "failed": failed_count,
            "pagination": pagination,
            "cases": [
                {"id": c.id, "title": ContentSanitizer.sanitize_for_log(c.title)}
                for c in created_cases
            ]
        }
