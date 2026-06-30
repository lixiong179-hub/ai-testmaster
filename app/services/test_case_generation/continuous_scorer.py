"""质量评分连续化模块（Task 8 / Task 14 三合一）。

7 维度连续评分委托 QualityScoringService.score_dimensions，权重统一在
quality_scoring_constants 定义。compute_continuous_score 作为向后兼容入口，
被 quality_validator.compute_quality_score 调用。

Task 14 前：本模块自带 7 个 _score_*_continuous 函数，与 grade_status
使用不同规则（如 _score_precondition_continuous 用合并 _LOGIN_MARKERS，
不检测登录状态矛盾），导致同一用例在 4 档判定与 7 维度评分间冲突。
Task 14 后：统一委托 score_dimensions，与 grade_status 共享 _classify_*
判定，消除冲突。
"""
from typing import Any, Dict

from app.services.case_quality.quality_scoring_constants import (
    WEIGHT_ACTION_TYPE,
    WEIGHT_ATOMICITY,
    WEIGHT_CASE_CATEGORY,
    WEIGHT_EXPECTED_RESULT,
    WEIGHT_PRECONDITION,
    WEIGHT_STEPS,
    WEIGHT_TITLE,
)
from app.services.case_quality.quality_scoring_service import QualityScoringService


def compute_continuous_score(case: Dict[str, Any]) -> float:
    """计算单条用例的连续化质量分（0~100）。

    委托 QualityScoringService.score_dimensions 计算 7 维度得分，加权
    求和后 * 10 转为 0-100 分制。与 grade_status 共享 _classify_* 判定，
    消除原 _score_*_continuous 与 grade_status 的规则冲突。

    Args:
        case: 单条测试用例字典

    Returns:
        质量分 0~100
    """
    dims = QualityScoringService.score_dimensions(case)
    weighted = (
        dims["title"] * WEIGHT_TITLE
        + dims["precondition"] * WEIGHT_PRECONDITION
        + dims["steps"] * WEIGHT_STEPS
        + dims["expected_result"] * WEIGHT_EXPECTED_RESULT
        + dims["case_category"] * WEIGHT_CASE_CATEGORY
        + dims["action_type"] * WEIGHT_ACTION_TYPE
        + dims["atomicity"] * WEIGHT_ATOMICITY
    )
    return round(weighted * 10, 1)
