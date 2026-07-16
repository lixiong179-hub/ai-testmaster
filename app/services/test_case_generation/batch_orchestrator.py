"""test_case_generation - 批量生成编排器（组合模式组件）。

合并自 batch_mixin.py + _coverage_enhancement_mixin.py
+ _module_failure_feedback_mixin.py，提供 BatchOrchestrator 类负责批量生成
测试用例的并发编排、类型覆盖补全与模块历史失败归因注入。

构造函数注入 context_builder / ai_generator / validator 三个组件引用，
对外保持 generate_test_cases_batch async generator 签名兼容。
"""
import asyncio
import copy
from typing import Any, Dict, List, Optional, AsyncGenerator

from loguru import logger
from sqlalchemy.orm import Session

from app.services.test_case_generation.helpers import ContentSanitizer


class BatchOrchestrator:
    """测试用例批量生成编排器。

    职责：
        1. 调用 context_builder 构建上下文，ai_generator 并发生成用例
        2. 类型覆盖补全（_enhance_coverage_for_point）
        3. 模块历史失败归因预加载与注入（_preload_module_failure_feedback / _refine_context_for_point）
        4. 调用 validator 持久化生成结果

    依赖通过构造函数注入：context_builder 提供 get_context_for_generation /
    enrich_context_with_trust_and_scoring，ai_generator 提供
    generate_test_case_for_point 与 _build_ui_description，validator 提供
    _save_test_case。
    """

    __test__ = False

    _DEFAULT_AI_CONCURRENCY = 3

    def __init__(
        self,
        db: Session,
        context_builder: Any,
        ai_generator: Any,
        validator: Any,
    ) -> None:
        self.db = db
        self._context_builder = context_builder
        self._ai_generator = ai_generator
        self._validator = validator

    # ── 并发控制 ──
    def _get_ai_generation_concurrency(self) -> int:
        from app.core.config import settings
        value = int(getattr(settings, "AI_CASE_GENERATION_CONCURRENCY", self._DEFAULT_AI_CONCURRENCY))
        return max(1, value)

    # ── 模块历史失败归因（合并自 _module_failure_feedback_mixin） ──
    def _preload_module_failure_feedback(
        self, project_id: int, test_points: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """批量预加载各模块的历史执行失败类型，消除 _refine_context_for_point 的 N+1 查询。

        业务原因：原实现每个测试点独立查询同模块失败用例，N 个测试点产生 N 次
        DB 查询。同 module 的测试点重复查询同一份数据。此处按 module IN(...) 一次
        查询全部，按模块分组取最近 5 条 failure_type，供 _refine_context_for_point
        从缓存读取。
        """
        modules = list({tp.get("module") for tp in test_points if tp.get("module")})
        if not modules:
            return {}
        db = getattr(self, "db", None)
        if db is None:
            return {}
        try:
            from app.models.test_case import TestCase
            rows = (
                db.query(TestCase.module, TestCase.execution_failure_type)
                .filter(
                    TestCase.project_id == project_id,
                    TestCase.module.in_(modules),
                    TestCase.execution_verified == False,  # noqa: E712
                    TestCase.is_deleted == False,  # noqa: E712
                )
                .order_by(TestCase.module, TestCase.last_verified_at.desc())
                .all()
            )
        except Exception as e:
            logger.warning(f"批量预加载历史执行失败归因失败: {e}")
            return {}

        grouped: Dict[str, List[str]] = {}
        for mod, ftype in rows:
            if mod not in grouped:
                grouped[mod] = []
            if len(grouped[mod]) < 5:
                grouped[mod].append(ftype or "other")
        return grouped

    async def _refine_context_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        module_failures: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """查询同模块历史执行失败归因并注入生成上下文（Task 12）。

        业务原因：同一模块的用例若历史上因元素定位失败/超时/断言失败等原因
        执行验证未通过（execution_verified=False），新一轮生成时应注入失败
        归因，指导AI避免同类问题。
        """
        module_name = test_point.get("module")
        if not module_name:
            return

        if module_failures is not None:
            failure_types: List[str] = module_failures.get(module_name, [])
        else:
            db = getattr(self, "db", None)
            if db is None:
                return
            try:
                from app.models.test_case import TestCase
                rows = (
                    db.query(TestCase.execution_failure_type)
                    .filter(
                        TestCase.project_id == project_id,
                        TestCase.module == module_name,
                        TestCase.execution_verified == False,  # noqa: E712
                        TestCase.is_deleted == False,  # noqa: E712
                    )
                    .order_by(TestCase.last_verified_at.desc())
                    .limit(5)
                    .all()
                )
                failure_types = [r[0] or "other" for r in rows]
            except Exception as e:
                logger.warning(f"查询历史执行失败归因失败: {e}")
                return

        if not failure_types:
            return

        failure_summary: Dict[str, int] = {}
        for ftype in failure_types:
            ftype = ftype or "other"
            failure_summary[ftype] = failure_summary.get(ftype, 0) + 1

        lines = [f"同模块历史上有 {len(failure_types)} 条用例执行失败，失败类型统计:"]
        for ftype, count in sorted(failure_summary.items(), key=lambda x: -x[1]):
            lines.append(f"  - {ftype}: {count}次")
        lines.append("请在新生成的用例中避免同类问题（如优化元素定位策略、增加等待逻辑、明确断言条件）。")
        context["execution_feedback"] = "\n".join(lines)

    # ── 类型覆盖补全（合并自 _coverage_enhancement_mixin） ──
    async def _enhance_coverage_for_point(
        self,
        candidate_cases: List[Dict[str, Any]],
        test_point: Dict[str, Any],
        point_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """检测类型覆盖缺失并补充生成缺失类型的用例。

        并发安全：point_context 已由调用方深拷贝，candidate_cases 为本测试点
        独有，generate_supplemental_cases 为纯函数不修改入参，故无需额外隔离。
        补全失败不影响主流程，仅记录告警并返回原候选列表。
        """
        from app.services.case_quality.coverage_service import (
            detect_missing_categories,
            generate_supplemental_cases,
        )
        from app.services.test_case_generation.ai_generator import _get_openai_client

        missing = detect_missing_categories(candidate_cases)
        if not missing:
            return candidate_cases

        try:
            ui_description = self._ai_generator._build_ui_description(
                point_context.get("ui_descriptions", [])
            )
            has_ui = bool(ui_description and ui_description.strip()) or bool(
                point_context.get("ui_specs", [])
            )
            supplemental_context: Dict[str, Any] = {
                "prd_content": point_context.get("requirement_content", ""),
                "ui_description": ui_description,
                "ui_specs": point_context.get("ui_specs", []),
                "existing_titles": [c.get("title", "") for c in candidate_cases],
                "has_ui": has_ui,
                "iteration_id": None,
            }
            supplemental = generate_supplemental_cases(
                missing_categories=missing,
                test_point=test_point,
                context=supplemental_context,
                ai_client=_get_openai_client(),
            )
            if supplemental:
                logger.info(
                    "批量生成覆盖补全 tp_id={} 补充{}条缺失类型用例: {}",
                    test_point.get("id"), len(supplemental), missing,
                )
                return candidate_cases + supplemental
        except (AttributeError, RuntimeError, ValueError, TypeError) as e:
            logger.warning(
                "批量生成覆盖补全失败 tp_id={} {}: {}",
                test_point.get("id"), type(e).__name__, e,
            )
        return candidate_cases

    # ── 主流程 ──
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
        """批量生成测试用例（流式输出）。

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
        context = await self._context_builder.get_context_for_generation(
            project_id=project_id,
            user_id=user_id,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_ids=test_point_ids,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size
        )

        if hasattr(self._context_builder, 'enrich_context_with_trust_and_scoring'):
            self._context_builder.enrich_context_with_trust_and_scoring(context, project_id)

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

        module_failures = self._preload_module_failure_feedback(project_id, test_points)

        async def _generate_one(index: int, point: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    point_context = copy.deepcopy(context)
                    await self._refine_context_for_point(
                        point_context, point, project_id, module_failures=module_failures
                    )
                    generated = await self._ai_generator.generate_test_case_for_point(
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
                candidate_cases = await self._enhance_coverage_for_point(
                    candidate_cases,
                    test_point,
                    result["point_context"],
                )
                saved_cases_for_point = []
                skipped_count = 0

                for candidate_case in candidate_cases:
                    try:
                        saved_case = await self._validator._save_test_case(
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


# 向后兼容别名：历史代码以 TestCaseGenerationBatchMixin 名称实例化
TestCaseGenerationBatchMixin = BatchOrchestrator
