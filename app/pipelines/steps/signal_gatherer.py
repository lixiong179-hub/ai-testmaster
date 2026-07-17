"""S1 SignalGatherer — 信号采集 Step

从迭代输入中采集需求文档、UI 原型、测试点等信号，
构建 Pipeline 后续 Step 所需的统一上下文产物。

辅助函数已拆分至 _signal_gatherer_helpers，本模块通过重新导出保持 import 路径不变。
"""
import hashlib
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
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
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["raw_signals"]

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
        history_sig = ctx.db.query(
            func.count(TestCase.id),
            func.max(TestCase.id),
            func.max(TestCase.update_time),
        ).filter(
            TestCase.project_id == iteration.project_id,
            TestCase.lifecycle_status != "archived",
            TestCase.is_deleted.is_(False),
        ).first()
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

        prd_content = ""
        ui_descriptions: List[Dict[str, Any]] = []
        ui_specs: List[Dict[str, Any]] = []
        test_points: List[Dict[str, Any]] = []
        change_notes_parts: List[str] = []
        file_ids_used: List[int] = []

        for inp in iteration.inputs:
            try:
                if inp.kind == "prd":
                    content = _load_file_content(ctx, inp.file_id, project_id)
                    if content:
                        prd_content += f"\n\n{content}"
                    if inp.file_id:
                        file_ids_used.append(inp.file_id)

                elif inp.kind == "prototype":
                    ui_desc, ui_spec, fids = _load_ui_from_input(ctx, inp, project_id)
                    ui_descriptions.extend(ui_desc)
                    ui_specs.extend(ui_spec)
                    file_ids_used.extend(fids)

                elif inp.kind == "testpoint":
                    points = _load_test_points_from_input(ctx, inp, project_id)
                    test_points.extend(points)

                elif inp.kind == "change_notes":
                    notes = _load_change_notes_from_input(inp)
                    if notes:
                        change_notes_parts.append(notes)

                elif inp.kind == "xmind":
                    content = _load_file_content(ctx, inp.file_id, project_id)
                    if content:
                        xmind_payload = {}
                        if inp.payload and isinstance(inp.payload, dict):
                            xmind_payload = dict(inp.payload)
                        xmind_payload["xmind_content"] = content
                        test_points.extend(_parse_xmind_to_testpoints(xmind_payload, project_id))

            except Exception as e:
                logger.error("信号采集失败 kind={} file_id={}: {}", inp.kind, inp.file_id, e)

        change_notes = "\n\n".join(change_notes_parts).strip()
        is_old_project = _check_is_old_project(ctx, project_id)

        if not prd_content and not ui_descriptions and not test_points and not change_notes and not is_old_project:
            return StepResult(
                success=False,
                error="迭代无有效输入信号（PRD/UI/测试点均为空）",
            )

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "prd_content": prd_content.strip(),
            "ui_descriptions": ui_descriptions,
            "ui_specs": ui_specs,
            "test_points": test_points,
            "change_notes": change_notes,
            "file_ids_used": file_ids_used,
            "has_ui": len(ui_specs) > 0,
            "has_prd": bool(prd_content.strip()),
            "has_testpoints": len(test_points) > 0,
            "has_change_notes": bool(change_notes),
            "is_old_project": is_old_project,
        }

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
                "file_ids": file_ids_used,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["iteration_id", "project_id", "prd_content", "test_points"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=False,
            error=f"信号采集降级: {error}",
            degraded=True,
        )
