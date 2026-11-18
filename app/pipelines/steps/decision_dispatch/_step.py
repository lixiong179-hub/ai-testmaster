import hashlib
import json
from typing import Any, ClassVar

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.decision_dispatch._builders import _validate_task_field
from app.pipelines.steps.decision_dispatch._fallback import _dispatch_fallback
from app.pipelines.steps.decision_dispatch._rules import get_action_rule


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
        aligned = ctx.get_artifact("aligned_testpoints")
        fingerprints = ctx.get_artifact("history_fingerprints")
        candidates = ctx.get_artifact("scenario_candidates")

        if merged is None:
            return StepResult(
                success=False,
                error="缺少 merged_verdicts 产物",
            )

        verdicts = merged.get("verdicts", [])
        fps = fingerprints.get("fingerprints", []) if fingerprints else []
        cands = candidates.get("candidates", []) if candidates else []
        _ = aligned.get("aligned_testpoints", []) if aligned else []

        fp_by_case_id: dict[int, dict[str, Any]] = {}
        for fp in fps:
            cid = fp.get("case_id")
            if cid is not None:
                fp_by_case_id[cid] = fp

        generation_tasks: list[dict[str, Any]] = []
        deprecation_suggestions: list[dict[str, Any]] = []
        budget_exhausted = False
        stats = {
            "keep_count": 0,
            "modify_count": 0,
            "create_count": 0,
            "locator_fix_count": 0,
            "deprecate_count": 0,
            "skip_count": 0,
            "conflict_count": 0,
        }

        for verdict in verdicts:
            if not isinstance(verdict, dict):
                continue

            if not ctx.check_budget():
                logger.warning(
                    "DecisionDispatch 预算耗尽，已生成 {} 条任务后暂停",
                    len(generation_tasks),
                )
                budget_exhausted = True
                break

            action = verdict.get("action", "")
            case_id = verdict.get("case_id")
            candidate_index = verdict.get("candidate_index")
            reason = verdict.get("reason", "")

            # R3-2：规则外置——分派查表，不再有 if/elif 动作判断链
            rule = get_action_rule(action)
            if rule is None:
                logger.warning("未知裁决动作 action={}, case_id={}，跳过", action, case_id)
                stats["skip_count"] += 1
                continue

            task, deprecation = rule["handler"](
                case_id=case_id,
                reason=reason,
                candidate_index=candidate_index,
                cands=cands,
                fp_by_case_id=fp_by_case_id,
                db=ctx.db,
            )
            if task is not None:
                generation_tasks.append(task)
            if deprecation is not None:
                deprecation_suggestions.append(deprecation)
            for stat_key in rule["stats"]:
                stats[stat_key] += 1

        project_id = merged.get("project_id", 0)

        skip_tasks = [t for t in generation_tasks if t.get("task_type") == "skip"]
        review_id = None
        if skip_tasks:
            try:
                from app.services.review_service import create_review, add_decision, start_review

                review = create_review(db=ctx.db, iteration_id=ctx.iteration_id, kind="merged")
                review_id = review.id
                start_review(db=ctx.db, review_id=review_id)
                for skip_task in skip_tasks:
                    skip_reason = skip_task.get("skip_reason", "")
                    case_id_for_verdict = skip_task.get("case_id") or 0
                    ai_verdict = "modify" if "冲突" in skip_reason else "keep"
                    add_decision(
                        db=ctx.db,
                        review_id=review_id,
                        target_kind="case",
                        target_id=case_id_for_verdict,
                        ai_verdict=ai_verdict,
                        ai_confidence=30,
                        ai_reason=skip_reason,
                    )
            except Exception as e:
                logger.error("自动创建审核记录失败: {}", e)

        payload = {
            "project_id": project_id,
            "generation_tasks": generation_tasks,
            "deprecation_suggestions": deprecation_suggestions,
            "stats": stats,
            "total_tasks": len(generation_tasks),
            "total_deprecations": len(deprecation_suggestions),
        }
        if review_id is not None:
            payload["review_id"] = review_id

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
