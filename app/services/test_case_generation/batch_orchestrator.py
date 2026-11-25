"""test_case_generation - 批量生成编排器（组合模式组件）。

合并自 batch_mixin.py + _coverage_enhancement_mixin.py
+ _module_failure_feedback_mixin.py，提供 BatchOrchestrator 类负责批量生成
测试用例的并发编排、类型覆盖补全与模块历史失败归因注入。

构造函数注入 context_builder / ai_generator / validator 三个组件引用，
对外保持 generate_test_cases_batch async generator 签名兼容。

拆分说明：模块历史失败归因与类型覆盖补全逻辑分别抽取至
ModuleFailureFeedbackMixin / CoverageEnhancementMixin（见同目录
_batch_orchestrator_failure_feedback.py / _batch_orchestrator_coverage.py），
本文件作为 thin wrapper 通过多继承组合并保留主流程编排与公开 API。
"""

import asyncio
import copy
from typing import Any
from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.orm import Session

from app.services.test_case_generation.helpers import ContentSanitizer
from app.services.test_case_generation._batch_orchestrator_failure_feedback import (
    ModuleFailureFeedbackMixin,
)
from app.services.test_case_generation._batch_orchestrator_coverage import (
    CoverageEnhancementMixin,
)


class BatchOrchestrator(ModuleFailureFeedbackMixin, CoverageEnhancementMixin):
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

    # ── 主流程 ──
    async def generate_test_cases_batch(
        self,
        project_id: int,
        user_id: int,
        test_point_ids: list[int] | None = None,
        requirement_file_ids: list[int] | None = None,
        ui_file_ids: list[int] | None = None,
        ui_screen_ids: list[int] | None = None,
        test_point_page: int = 1,
        test_point_page_size: int = 100,
        case_type: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
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
            test_point_page_size=test_point_page_size,
        )

        if hasattr(self._context_builder, "enrich_context_with_trust_and_scoring"):
            self._context_builder.enrich_context_with_trust_and_scoring(context, project_id)

        context_stats = context.get("context_stats", {})
        warnings = context.get("warnings", [])
        evidence_refs = context.get("evidence_refs", {})

        yield {
            "progress": 5,
            "message": "获取上下文信息",
            "status": "running",
            "context_stats": context_stats,
            "warnings": warnings,
            "evidence_refs": evidence_refs,
        }

        if warnings:
            for warning in warnings[:3]:
                yield _build_warning_event(warning)

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
            "pagination": pagination,
        }

        created_cases = []
        failed_count = 0

        primary_requirement_file_id = requirement_file_ids[0] if requirement_file_ids else None
        # 模块级信号量限制跨请求总 AI 并发（P-2 修复）；
        # concurrency 仅用于进度提示，实际并发上限由 settings.AI_CASE_GENERATION_CONCURRENCY 控制
        concurrency = self._get_ai_generation_concurrency()

        module_failures = self._preload_module_failure_feedback(project_id, test_points)

        yield {
            "progress": 10,
            "message": f"AI并发生成已启动，并发数{concurrency}",
            "status": "running",
            "total": total,
            "concurrency": concurrency,
        }

        generation_tasks = [
            asyncio.create_task(
                self._generate_point_result(
                    index=i,
                    point=test_point,
                    context=context,
                    project_id=project_id,
                    case_type=case_type,
                    module_failures=module_failures,
                )
            )
            for i, test_point in enumerate(test_points)
        ]

        for completed, task in enumerate(asyncio.as_completed(generation_tasks), 1):
            result = await task
            i = result["index"]
            test_point = result["test_point"]
            generated_case = result["generated_case"]
            if result["error"] is not None or generated_case is None:
                failed_count += 1
                yield _build_point_failure_event(i, completed, total, failed_count)
                continue

            try:
                saved_cases_for_point, skipped_count = await self._save_point_cases(
                    generated_case=generated_case,
                    test_point=test_point,
                    point_context=result["point_context"],
                    project_id=project_id,
                    requirement_file_id=primary_requirement_file_id,
                )
                failed_count += skipped_count
                created_cases.extend(saved_cases_for_point)
                yield _build_point_success_event(i, completed, total, saved_cases_for_point, skipped_count)
            except Exception as e:
                failed_count += 1
                logger.error(f"生成测试用例失败: {e}")
                yield _build_point_error_event(i, total, failed_count)

        yield _build_batch_summary_event(created_cases, failed_count, total, pagination)

    async def _generate_point_result(
        self,
        index: int,
        point: dict[str, Any],
        context: dict[str, Any],
        project_id: int,
        case_type: str | None,
        module_failures: dict[str, Any],
    ) -> dict[str, Any]:
        """并发单元：为单个测试点生成用例；失败转成带 error 的结果而不抛出。"""
        from app.utils.ai_concurrency import ai_generation_slot

        async with ai_generation_slot():
            try:
                point_context = copy.deepcopy(context)
                await self._refine_context_for_point(point_context, point, project_id, module_failures=module_failures)
                generated = await self._ai_generator.generate_test_case_for_point(
                    context=point_context, test_point=point, project_id=project_id, case_type=case_type
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

    async def _save_point_cases(
        self,
        generated_case: dict[str, Any],
        test_point: dict[str, Any],
        point_context: dict[str, Any],
        project_id: int,
        requirement_file_id: int | None,
    ) -> tuple[list[Any], int]:
        """覆盖率补全 + 逐条落库；被质量门拒绝的用例计入 skipped。"""
        candidate_cases = [generated_case]
        candidate_cases.extend(generated_case.get("_extra_cases", []))
        candidate_cases = await self._enhance_coverage_for_point(candidate_cases, test_point, point_context)

        saved_cases: list[Any] = []
        skipped_count = 0
        for candidate_case in candidate_cases:
            try:
                saved_case = await self._validator._save_test_case(
                    project_id=project_id,
                    generated_case=candidate_case,
                    test_point=test_point,
                    requirement_file_id=requirement_file_id,
                )
                saved_cases.append(saved_case)
            except Exception as save_e:
                skipped_count += 1
                logger.warning(f"case skipped by generation quality gate: {save_e}")
        return saved_cases, skipped_count


def _build_warning_event(warning: Any) -> dict[str, Any]:
    """上下文告警 → SSE 事件（dict 告警保留原始结构，字符串补 UNKNOWN 码）。"""
    if isinstance(warning, dict):
        return {
            "progress": 5,
            "message": str(warning.get("message", "")),
            "status": "warning",
            "warning_detail": warning,
        }
    return {
        "progress": 5,
        "message": str(warning),
        "status": "warning",
        "warning_detail": {"message": str(warning), "code": "UNKNOWN"},
    }


def _build_point_failure_event(index: int, completed: int, total: int, failed_count: int) -> dict[str, Any]:
    """并发生成阶段该测试点直接失败（按已完成数量推进）。"""
    return {
        "progress": int(10 + completed / total * 85),
        "message": f"生成第{index + 1}个用例失败",
        "status": "running",
        "error": True,
        "failed_count": failed_count,
        "current": completed,
        "total": total,
    }


def _build_point_error_event(index: int, total: int, failed_count: int) -> dict[str, Any]:
    """落库/补全阶段抛错（按测试点序号推进，与原实现一致）。"""
    return {
        "progress": int(10 + (index + 1) / total * 85),
        "message": f"生成第{index + 1}个用例失败",
        "status": "running",
        "error": True,
        "failed_count": failed_count,
    }


def _build_point_success_event(
    index: int,
    completed: int,
    total: int,
    saved_cases: list[Any],
    skipped_count: int,
) -> dict[str, Any]:
    """单测试点完成事件：`case` 取该点首条落库用例（无则 None）。"""
    case_payload = None
    if saved_cases:
        first_saved = saved_cases[0]
        case_payload = {
            "id": first_saved.id,
            "title": ContentSanitizer.sanitize_for_log(first_saved.title),
            "module": first_saved.module,
        }
    return {
        "progress": int(10 + completed / total * 85),
        "message": f"已生成{index + 1}/{total}个测试用例",
        "status": "running",
        "current": completed,
        "total": total,
        "case": case_payload,
        "saved_count": len(saved_cases),
        "skipped_count": skipped_count,
    }


def _build_batch_summary_event(
    created_cases: list[Any],
    failed_count: int,
    total: int,
    pagination: dict[str, Any],
) -> dict[str, Any]:
    return {
        "progress": 100,
        "message": f"完成！成功{len(created_cases)}个，失败{failed_count}个",
        "status": "success" if failed_count == 0 else "partial",
        "total": total,
        "created": len(created_cases),
        "failed": failed_count,
        "pagination": pagination,
        "cases": [{"id": c.id, "title": ContentSanitizer.sanitize_for_log(c.title)} for c in created_cases],
    }


# 向后兼容别名：历史代码以 TestCaseGenerationBatchMixin 名称实例化
TestCaseGenerationBatchMixin = BatchOrchestrator
