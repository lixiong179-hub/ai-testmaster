"""
Test Case Generation Service - 批量生成Mixin
包含批量生成测试用例的流式输出逻辑
"""
import asyncio
import copy
from typing import List, Dict, Any, Optional, AsyncGenerator
from loguru import logger

from app.services.test_case_generation.base_mixin import ContentSanitizer


class TestCaseGenerationBatchMixin:
    """测试用例生成服务 - 批量生成Mixin"""

    _DEFAULT_AI_CONCURRENCY = 3

    def _get_ai_generation_concurrency(self) -> int:
        from app.core.config import settings
        value = int(getattr(settings, "AI_CASE_GENERATION_CONCURRENCY", self._DEFAULT_AI_CONCURRENCY))
        return max(1, value)

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
        from app.services.test_case_generation.ai_mixin import _get_openai_client

        missing = detect_missing_categories(candidate_cases)
        if not missing:
            return candidate_cases

        try:
            ui_description = self._build_ui_description(
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
            # R7 修复：收窄 except 范围，仅捕获预期异常：
            # - AttributeError: settings 配置缺失 / ui_desc 数据结构异常
            # - RuntimeError: OpenAI 客户端初始化失败
            # - ValueError / TypeError: supplemental_context 构造或数据类型错误
            # generate_supplemental_cases 内部已对 AI 调用 try/except 兜底返回 []，
            # 故外层不会遇到网络/解析异常。未预期的异常应冒泡到 _generate_one
            # 由其 except 兜底，避免静默吞掉编程错误。
            logger.warning(
                "批量生成覆盖补全失败 tp_id={} {}: {}",
                test_point.get("id"), type(e).__name__, e,
            )
        return candidate_cases

    def _preload_module_failure_feedback(
        self, project_id: int, test_points: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """批量预加载各模块的历史执行失败类型，消除 _refine_context_for_point 的 N+1 查询。

        业务原因：原实现每个测试点独立查询同模块失败用例，N 个测试点产生 N 次
        DB 查询。同 module 的测试点重复查询同一份数据。此处按 module IN(...) 一次
        查询全部，按模块分组取最近 5 条 failure_type，供 _refine_context_for_point
        从缓存读取。

        Args:
            project_id: 项目ID。
            test_points: 测试点列表（用于提取 distinct module 集合）。

        Returns:
            {module_name: [failure_type, ...]} 映射，每组最多 5 条。
        """
        modules = list({tp.get("module") for tp in test_points if tp.get("module")})
        if not modules:
            return {}
        db = getattr(self, "db", None)
        if db is None:
            return {}
        try:
            from app.models.test_case import TestCase
            # 只查 failure_type 字段（轻量），按 module + last_verified_at 排序保证
            # 每组取最近 5 条，与原单点查询语义一致
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

        Args:
            context: 生成上下文字典，原地修改注入 execution_feedback 键。
            test_point: 当前测试点字典（用于提取 module 字段确定同模块范围）。
            project_id: 项目ID。
            module_failures: 批量预加载的 {module: [failure_type]} 缓存。
                传入时从缓存读取（R4 修复，消除 N+1）；未传入时回退单点查询保持兼容。
        """
        module_name = test_point.get("module")
        if not module_name:
            return

        if module_failures is not None:
            failure_types: List[str] = module_failures.get(module_name, [])
        else:
            # 回退路径：未预加载时单点查询（直接调用本方法的场景）
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
