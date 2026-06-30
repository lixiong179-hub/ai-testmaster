from typing import Any, Dict, Optional

from loguru import logger

from app.services.case_quality.quality_scoring_service import QualityScoringService
from app.services.quality.grade import score_to_grade


def _score_to_grade(score: float) -> str:
    """委托共享工具 score_to_grade，保持 pipelines 模块向后兼容的私有别名。

    score 必为 float（调用方保证非 None），故校验非 None 后取值。
    使用 raise 而非 assert，避免 -O 模式下被移除。
    """
    grade = score_to_grade(score)
    if grade is None:
        raise RuntimeError(f"score_to_grade returned None for score={score}")
    return grade


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
    user_confirmed: Optional[bool] = None,
) -> tuple[float, str, Dict[str, float]]:
    """计算 prior 质量分。

    Args:
        case_data: 单条用例数据。
        tp: 测试点信息。
        signals: raw_signals 产物。
        inferred: inferred_business_summary 产物。
        aligned: aligned_testpoints 产物。
        iteration_id: 迭代 ID。
        db: 数据库会话，仅在 user_confirmed 未传入时查询。
        user_confirmed: 用户已确认标记。生产调用方应在循环前调用一次
            _check_user_confirmed 后传入，避免循环内 N+1 查询。
            None 表示未传入，函数内部回退到查询 DB（保留向后兼容）。
    """
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

    # 调用方在循环前查询一次传入，避免 N+1；None 时回退到 DB 查询（向后兼容）
    if user_confirmed is None:
        confirmed = _check_user_confirmed(db, iteration_id)
    else:
        confirmed = user_confirmed
    confirmed_score = 15.0 if confirmed else 0.0
    signal_breakdown["user_confirmed"] = confirmed_score
    signal_score += confirmed_score

    conflict_count = aligned.get("conflict_count", 0)
    conflict_penalty = min(15.0, conflict_count * 3.0)
    signal_breakdown["conflict_penalty"] = -conflict_penalty
    signal_score -= conflict_penalty

    signal_score = max(0.0, min(100.0, signal_score))

    # Task 14 三合一：content 部分委托 QualityScoringService.prior_score，
    # 与 grade_status/score_dimensions 共享统一常量与 _classify_* 判定
    content_score, content_breakdown = QualityScoringService.prior_score(case_data)

    final_score = round(0.4 * signal_score + 0.6 * content_score, 2)
    final_score = max(0.0, min(100.0, final_score))

    breakdown: Dict[str, float] = {}
    breakdown["signal_score"] = round(signal_score, 2)
    breakdown["content_score"] = round(content_score, 2)
    breakdown.update(signal_breakdown)
    breakdown.update(content_breakdown)

    grade = _score_to_grade(final_score)
    return round(final_score, 2), grade, breakdown
