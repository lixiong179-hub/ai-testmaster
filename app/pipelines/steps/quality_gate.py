"""S12 QualityGate — 先验质量门 Step

对生成的用例做先验质量评估，计算质量分和等级。
基于 plan §7.1 信号完整性公式。
"""
import hashlib
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class QualityGate(PipelineStep):
    """先验质量门 Step — 评估生成用例的先验质量分。"""

    name: ClassVar[str] = "quality_gate"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["generated_cases"]
    produces: ClassVar[List[str]] = ["quality_scores"]

    def should_run(self, ctx: PipelineContext) -> bool:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return False
        return cases.get("success_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return ""
        case_titles = []
        for entry in cases.get("generated_cases", []):
            if entry.get("status") == "success":
                for cd in entry.get("case_data", []):
                    case_titles.append(cd.get("title", ""))
        raw = f"{self.name}:{self.version}:titles={sorted(case_titles)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        cases_artifact = ctx.get_artifact("generated_cases")
        if not cases_artifact:
            return StepResult(success=False, error="缺少 generated_cases 产物")

        signals = ctx.get_artifact("raw_signals") or {}
        inferred = ctx.get_artifact("inferred_business_summary") or {}
        aligned = ctx.get_artifact("aligned_testpoints") or {}

        generated_cases = cases_artifact.get("generated_cases", [])
        scores = []
        total_score = 0.0
        graded_count = 0

        for entry in generated_cases:
            if entry.get("status") != "success":
                continue

            case_data_list = entry.get("case_data", [])
            tp = entry.get("test_point", {})

            for case_data in case_data_list:
                score, grade, breakdown = _compute_prior_score(
                    case_data, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                )
                scores.append({
                    "test_point_id": tp.get("id"),
                    "case_title": case_data.get("title", ""),
                    "score": score,
                    "grade": grade,
                    "breakdown": breakdown,
                    "lifecycle_status": case_data.get("lifecycle_status", "draft"),
                })
                total_score += score
                graded_count += 1

                if grade == "D":
                    case_data["lifecycle_status"] = "pending_review"

        avg_score = total_score / graded_count if graded_count > 0 else 0.0
        avg_grade = _score_to_grade(avg_score)

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": cases_artifact.get("project_id"),
            "scores": scores,
            "total_graded": graded_count,
            "average_score": round(avg_score, 2),
            "average_grade": avg_grade,
            "needs_review_count": len([s for s in scores if s["grade"] == "D"]),
        }

        confidence = min(avg_score / 100.0, 1.0)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="quality_scores",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "avg_score": avg_score,
                "avg_grade": avg_grade,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "scores" in payload and "average_score" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        cases_artifact = ctx.get_artifact("generated_cases")
        generated_cases = cases_artifact.get("generated_cases", []) if cases_artifact else []
        scores = []
        for entry in generated_cases:
            if entry.get("status") != "success":
                continue
            for case_data in entry.get("case_data", []):
                scores.append({
                    "test_point_id": entry.get("test_point", {}).get("id"),
                    "case_title": case_data.get("title", ""),
                    "score": 50.0,
                    "grade": "C",
                    "breakdown": {"fallback": True},
                    "lifecycle_status": "pending_review",
                })

        return StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "scores": scores,
                "total_graded": len(scores),
                "average_score": 50.0,
                "average_grade": "C",
                "needs_review_count": len(scores),
            },
            artifact_kind="quality_scores",
            artifact_confidence=0.3,
            degraded=True,
        )


def _compute_prior_score(
    case_data: Dict[str, Any],  # 保留用于未来内容维度扩展（title/steps/precondition 等）
    tp: Dict[str, Any],  # 保留用于未来测试点关联度评估
    signals: Dict[str, Any],
    inferred: Dict[str, Any],
    aligned: Dict[str, Any],
    iteration_id: int,
    db: Any,
) -> tuple[float, str, Dict[str, float]]:
    score = 0.0
    breakdown: Dict[str, float] = {}

    signals = signals or {}
    inferred = inferred or {}
    aligned = aligned or {}

    has_prd = signals.get("has_prd", False)
    has_testpoints = signals.get("has_testpoints", False)
    has_ui = signals.get("has_ui", False)
    has_history = signals.get("is_old_project", False)

    if has_prd:
        prd_score = 25.0
        breakdown["prd"] = prd_score
        score += prd_score
    else:
        inferred_confidence = inferred.get("confidence", 0.0)
        caps_score = round(inferred_confidence * 15, 2)
        breakdown["inferred_capability_confidence"] = caps_score
        score += caps_score

    tp_score = 20.0 if has_testpoints else 0.0
    breakdown["testpoints"] = tp_score
    score += tp_score

    ui_score = 25.0 if has_ui else 0.0
    breakdown["ui_prototype"] = ui_score
    score += ui_score

    history_score = 15.0 if has_history else 5.0
    breakdown["history"] = history_score
    score += history_score

    confirmed = _check_user_confirmed(db, iteration_id)
    confirmed_score = 15.0 if confirmed else 0.0
    breakdown["user_confirmed"] = confirmed_score
    score += confirmed_score

    conflict_count = aligned.get("conflict_count", 0)
    conflict_penalty = min(15.0, conflict_count * 3.0)
    breakdown["conflict_penalty"] = -conflict_penalty
    score -= conflict_penalty

    score = max(0.0, min(100.0, score))
    grade = _score_to_grade(score)
    return round(score, 2), grade, breakdown


def _check_user_confirmed(db: Any, iteration_id: int) -> bool:
    if db is None:
        return False
    from app.models.iteration import IterationInput

    supplement = db.query(IterationInput).filter(
        IterationInput.iteration_id == iteration_id,
        IterationInput.kind == "supplement",
    ).first()
    return supplement is not None


def _score_to_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    return "D"
