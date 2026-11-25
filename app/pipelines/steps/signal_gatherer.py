"""S1 SignalGatherer — 信号采集 Step

从迭代输入中采集需求文档、UI 原型、测试点等信号，
构建 Pipeline 后续 Step 所需的统一上下文产物。

辅助函数已拆分至 _signal_gatherer_helpers，本模块通过重新导出保持 import 路径不变。
"""

import hashlib
from typing import Any, ClassVar

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps._signal_gatherer_collect import _collect_input_signals
from app.pipelines.steps._signal_gatherer_helpers import (
    _load_file_content,
    _load_change_notes_from_input,
    _load_ui_from_input,
    _load_test_points_from_input,
    _check_is_old_project,
    _parse_xmind_to_testpoints,
    _compute_signal_confidence,
    _format_test_point,
    _collect_ui_screen_ids,
    _collect_prototype_project_ids,
    _coerce_id_list,
)

__all__ = [
    "SignalGatherer",
    # 重新导出辅助函数以保持 import 路径不变
    "_load_file_content",
    "_load_change_notes_from_input",
    "_load_ui_from_input",
    "_load_test_points_from_input",
    "_check_is_old_project",
    "_parse_xmind_to_testpoints",
    "_compute_signal_confidence",
    "_format_test_point",
    "_collect_ui_screen_ids",
    "_collect_prototype_project_ids",
    "_coerce_id_list",
]


class SignalGatherer(PipelineStep):
    """信号采集 Step — 从迭代输入加载 PRD / UI / 测试点。"""

    name: ClassVar[str] = "signal_gatherer"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[list[str]] = []
    produces: ClassVar[list[str]] = ["raw_signals"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        from app.models.iteration import Iteration
        from app.models.test_case import TestCase
        from sqlalchemy import func

        iteration = ctx.db.query(Iteration).filter_by(id=ctx.iteration_id).first()
        if not iteration:
            return ""
        input_hashes = []
        for inp in sorted(iteration.inputs, key=lambda i: i.id):
            input_hashes.append(inp.content_hash or "")
        history_sig = (
            ctx.db.query(
                func.count(TestCase.id),
                func.max(TestCase.id),
                func.max(TestCase.update_time),
            )
            .filter(
                TestCase.project_id == iteration.project_id,
                TestCase.lifecycle_status != "archived",
                TestCase.is_deleted.is_(False),
            )
            .first()
        )
        raw = (
            f"{self.name}:{self.version}:iteration={iteration.id}:project={iteration.project_id}:"
            f"history={history_sig}:{':'.join(input_hashes)}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        from app.models.iteration import Iteration

        iteration = ctx.db.query(Iteration).filter_by(id=ctx.iteration_id).first()
        if not iteration:
            return StepResult(
                success=False,
                error=f"迭代 {ctx.iteration_id} 不存在",
            )

        project_id = iteration.project_id
        bundle = _collect_input_signals(ctx, iteration.inputs, project_id)
        is_old_project = _check_is_old_project(ctx, project_id)

        if bundle.is_empty() and not is_old_project:
            return StepResult(
                success=False,
                error="迭代无有效输入信号（PRD/UI/测试点均为空）",
            )

        payload = bundle.to_payload(ctx, project_id, is_old_project)
        confidence = _compute_signal_confidence(payload)
        if confidence == 0.0 and is_old_project:
            confidence = 0.2

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="raw_signals",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "input_count": len(iteration.inputs),
                "file_ids": bundle.file_ids_used,
            },
        )

    def validate_output(self, payload: dict[str, Any]) -> bool:
        required = ["iteration_id", "project_id", "prd_content", "test_points"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> StepResult | None:
        return StepResult(
            success=False,
            error=f"信号采集降级: {error}",
            degraded=True,
        )
