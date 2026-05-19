import hashlib
from typing import Any, ClassVar, Dict, List, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.reconciliation._merge import (
    MergedAction,
    merge,
    _verdict_to_dict,
    _compute_reconciliation_stats,
    _compute_avg_confidence,
    _record_conflict_metric,
)


class Reconciliation(PipelineStep):
    name: ClassVar[str] = "reconciliation"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["backward_verdicts", "forward_verdicts"]
    produces: ClassVar[List[str]] = ["merged_verdicts"]

    def should_run(self, ctx: PipelineContext) -> bool:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")
        return backward is not None or forward is not None

    def cache_key(self, ctx: PipelineContext) -> str:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")
        bw_count = backward.get("total_count", 0) if backward else 0
        fw_count = forward.get("total_count", 0) if forward else 0
        raw = f"{self.name}:{self.version}:bw={bw_count}:fw={fw_count}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")

        backward_verdicts = backward.get("verdicts", []) if backward else []
        forward_verdicts = forward.get("verdicts", []) if forward else []

        project_id = 0
        if backward:
            project_id = backward.get("project_id", 0)
        elif forward:
            project_id = forward.get("project_id", 0)

        merged = merge(backward_verdicts, forward_verdicts)

        conflict_count = sum(1 for v in merged if v.conflict_marker)
        if conflict_count > 0:
            _record_conflict_metric(db=ctx.db, project_id=project_id, detail={"conflict_count": conflict_count})

        payload = {
            "project_id": project_id,
            "verdicts": [_verdict_to_dict(v) for v in merged],
            "total_count": len(merged),
            "stats": _compute_reconciliation_stats(merged),
        }

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="merged_verdicts",
            artifact_confidence=_compute_avg_confidence(merged),
            artifact_provenance={"step": self.name, "version": self.version, "total_count": len(merged)},
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "verdicts", "total_count", "stats"]
        return all(k in payload for k in required) and payload["total_count"] == len(payload["verdicts"])

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")
        project_id = 0
        if backward:
            project_id = backward.get("project_id", 0)
        elif forward:
            project_id = forward.get("project_id", 0)
        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id, "verdicts": [], "total_count": 0,
                "stats": {"keep": 0, "needs_modify": 0, "locator_broken": 0,
                          "locator_and_modify": 0, "deprecate": 0, "add_new": 0,
                          "conflict": 0, "pending_review": 0},
            },
            artifact_kind="merged_verdicts",
            artifact_confidence=0.0,
            artifact_provenance={"step": self.name, "version": self.version, "degraded": True, "error": str(error)},
            degraded=True,
        )
