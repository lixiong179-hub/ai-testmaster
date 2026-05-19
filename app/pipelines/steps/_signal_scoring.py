from typing import Any, Dict

from loguru import logger

from app.pipelines.steps._scoring import (
    _score_title,
    _score_steps,
    _score_expected_result,
    _score_precondition,
)


def _score_to_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def _check_user_confirmed(db: Any, iteration_id: int) -> bool:
    if db is None:
        return False
    from app.models.iteration import IterationInput

    supplement = db.query(IterationInput).filter(
        IterationInput.iteration_id == iteration_id,
        IterationInput.kind == "supplement",
    ).first()
    return supplement is not None


def _compute_analyzer_score(
    analyzer: Any,
    case_data: Dict[str, Any],
) -> tuple[float, str, Dict[str, float]]:
    result = analyzer.analyze_case(case_data)

    complexity_score = result["complexity_score"]
    coverage_score = result["coverage_score"]
    redundancy_score = result["redundancy_score"]
    suggestion_count = result["suggestion_count"]

    complexity_norm = (10 - complexity_score) / 10 * 100
    coverage_norm = coverage_score / 10 * 100
    redundancy_norm = (10 - redundancy_score) / 10 * 100
    suggestion_norm = max(0, 100 - suggestion_count * 10)

    score = complexity_norm * 0.3 + coverage_norm * 0.3 + redundancy_norm * 0.2 + suggestion_norm * 0.2
    score = max(0.0, min(100.0, round(score, 2)))

    breakdown: Dict[str, float] = {
        "analyzer_complexity": round(complexity_score, 2),
        "analyzer_coverage": round(coverage_score, 2),
        "analyzer_redundancy": round(redundancy_score, 2),
        "analyzer_suggestion_count": float(suggestion_count),
        "complexity_norm": round(complexity_norm, 2),
        "coverage_norm": round(coverage_norm, 2),
        "redundancy_norm": round(redundancy_norm, 2),
        "suggestion_norm": round(suggestion_norm, 2),
    }

    grade = _score_to_grade(score)
    return score, grade, breakdown


def _compute_prior_score(
    case_data: Dict[str, Any],
    tp: Dict[str, Any],
    signals: Dict[str, Any],
    inferred: Dict[str, Any],
    aligned: Dict[str, Any],
    iteration_id: int,
    db: Any,
) -> tuple[float, str, Dict[str, float]]:
    signal_score = 0.0
    signal_breakdown: Dict[str, float] = {}

    signals = signals or {}
    inferred = inferred or {}
    aligned = aligned or {}

    has_prd = signals.get("has_prd", False)
    has_testpoints = signals.get("has_testpoints", False)
    has_ui = signals.get("has_ui", False)
    has_history = signals.get("is_old_project", False)

    if has_prd:
        prd_score = 25.0
        signal_breakdown["prd"] = prd_score
        signal_score += prd_score
    else:
        inferred_confidence = inferred.get("confidence", 0.0)
        caps_score = round(inferred_confidence * 15, 2)
        signal_breakdown["inferred_capability_confidence"] = caps_score
        signal_score += caps_score

    tp_score = 20.0 if has_testpoints else 0.0
    signal_breakdown["testpoints"] = tp_score
    signal_score += tp_score

    ui_score = 25.0 if has_ui else 0.0
    signal_breakdown["ui_prototype"] = ui_score
    signal_score += ui_score

    history_score = 15.0 if has_history else 5.0
    signal_breakdown["history"] = history_score
    signal_score += history_score

    confirmed = _check_user_confirmed(db, iteration_id)
    confirmed_score = 15.0 if confirmed else 0.0
    signal_breakdown["user_confirmed"] = confirmed_score
    signal_score += confirmed_score

    conflict_count = aligned.get("conflict_count", 0)
    conflict_penalty = min(15.0, conflict_count * 3.0)
    signal_breakdown["conflict_penalty"] = -conflict_penalty
    signal_score -= conflict_penalty

    signal_score = max(0.0, min(100.0, signal_score))

    content_score = 0.0
    content_breakdown: Dict[str, float] = {}

    title_score = _score_title(case_data.get("title", ""))
    content_breakdown["title_quality"] = title_score
    content_score += title_score

    case_type = case_data.get("case_type", "")
    steps_score = _score_steps(case_data.get("steps", []), case_type=case_type)
    content_breakdown["steps_quality"] = steps_score
    content_score += steps_score

    expected_score = _score_expected_result(case_data.get("expected_result", ""))
    content_breakdown["expected_result_quality"] = expected_score
    content_score += expected_score

    precondition_score = _score_precondition(case_data.get("precondition", ""))
    content_breakdown["precondition_quality"] = precondition_score
    content_score += precondition_score

    content_score = max(0.0, min(100.0, content_score))

    final_score = round(0.4 * signal_score + 0.6 * content_score, 2)
    final_score = max(0.0, min(100.0, final_score))

    breakdown: Dict[str, float] = {}
    breakdown["signal_score"] = round(signal_score, 2)
    breakdown["content_score"] = round(content_score, 2)
    breakdown.update(signal_breakdown)
    breakdown.update(content_breakdown)

    grade = _score_to_grade(final_score)
    return round(final_score, 2), grade, breakdown
