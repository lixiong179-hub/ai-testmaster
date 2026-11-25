import hashlib
import json
from typing import Any, ClassVar

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.decision_dispatch._builders import _validate_task_field
from app.pipelines.steps.decision_dispatch._execute_loop import (
    _build_fp_index,
    _build_payload,
    _create_skip_review,
    _run_verdicts,
)
from app.pipelines.steps.decision_dispatch._fallback import _dispatch_fallback


_KEEP = "keep"
_NEEDS_MODIFY = "needs_modify"
_LOCATOR_BROKEN = "locator_broken"
_LOCATOR_AND_MODIFY = "locator_and_modify"
_DEPRECATE = "deprecate"
_ADD_NEW = "add_new"
_CONFLICT = "conflict"
_PENDING_REVIEW = "pending_review"


class DecisionDispatch(PipelineStep):
    name: ClassVar[str] = "decision_dispatch"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[list[str]] = [
        "merged_verdicts",
        "aligned_testpoints",
        "history_fingerprints",
        "scenario_candidates",
    ]
    produces: ClassVar[list[str]] = ["generation_tasks"]

    def should_run(self, ctx: PipelineContext) -> bool:
        merged = ctx.get_artifact("merged_verdicts")
        if merged is None:
            return False
        verdicts = merged.get("verdicts", [])
        total = merged.get("total_count", 0)
        return len(verdicts) > 0 and total > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        merged = ctx.get_artifact("merged_verdicts")
        if merged is None:
            return hashlib.sha256(f"{self.name}:{self.version}:empty".encode()).hexdigest()
        verdicts = merged.get("verdicts", [])
        verdict_hash = hashlib.sha256(json.dumps(verdicts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[
            :16
        ]
        raw = f"{self.name}:{self.version}:verdicts={verdict_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        merged = ctx.get_artifact("merged_verdicts")
        if merged is None:
            return StepResult(
                success=False,
                error="缺少 merged_verdicts 产物",
            )

        fingerprints = ctx.get_artifact("history_fingerprints")
        candidates = ctx.get_artifact("scenario_candidates")
        fps = fingerprints.get("fingerprints", []) if fingerprints else []
        cands = candidates.get("candidates", []) if candidates else []

        generation_tasks, deprecation_suggestions, stats, budget_exhausted = _run_verdicts(
            ctx,
            merged.get("verdicts", []),
            cands,
            _build_fp_index(fps),
        )
        review_id = _create_skip_review(ctx, generation_tasks)
        payload = _build_payload(
            merged.get("project_id", 0),
            generation_tasks,
            deprecation_suggestions,
            stats,
            review_id,
        )

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="generation_tasks",
            artifact_confidence=1.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_tasks": len(generation_tasks),
                "total_deprecations": len(deprecation_suggestions),
                "stats": stats,
                "budget_exhausted": budget_exhausted,
            },
            pause_for_confirmation=budget_exhausted,
            confirmation_reason=(f"Token 预算耗尽，已生成 {len(generation_tasks)} 条任务，剩余裁决未处理，等待用户确认")
            if budget_exhausted
            else None,
            confirmation_payload=payload if budget_exhausted else None,
        )

    def validate_output(self, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        tasks = payload.get("generation_tasks")
        if not isinstance(tasks, list):
            return False
        if tasks and not all(_validate_task_field(t) for t in tasks):
            return False
        stats = payload.get("stats")
        if not isinstance(stats, dict):
            return False
        required_stats = [
            "keep_count",
            "modify_count",
            "create_count",
            "locator_fix_count",
            "deprecate_count",
            "skip_count",
            "conflict_count",
        ]
        return all(k in stats for k in required_stats)

    def fallback(self, ctx: PipelineContext, error: Exception) -> StepResult | None:
        return _dispatch_fallback(self.name, self.version, ctx, error)
