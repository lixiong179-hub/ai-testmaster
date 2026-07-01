"""测试用例质量校验器。

对 AI 生成的测试用例进行语义质量校验，确保入库前满足质量标准。
校验不通过时返回具体问题描述，供重试反馈使用。

校验维度:
    - 标题质量：禁止模糊词、长度限制
    - 前置条件完整性：须含登录状态和网络环境
    - 步骤完整性：非空、原子性、确定性、自动化可执行性
    - 预期结果质量：禁止模糊描述
    - case_category 合法性
    - 用例数量达标
    - 原子性：标题不应同时包含主流程+分支/旁路逻辑
    - 边界值策略：boundary 用例须使用实际边界值而非占位符
    - 类型一致性：case_type 与 action_type 组合不可矛盾

拆分说明:
    - 字段级校验（validate_title/validate_precondition/validate_expected_result/
      validate_case_category）拆分至 _quality_field_validators
    - 步骤级校验（validate_steps/validate_test_data_quality/
      validate_boundary_strategy/validate_type_consistency）拆分至
      _quality_step_validators；本模块 re-export 全部函数保持导入兼容
    - 编排函数（validate_single_case/validate_single_case_status/
      validate_cases_quality/compute_quality_score）保留在此模块
"""
from typing import List, Dict, Any, Tuple

from app.services.case_quality.quality_scoring_constants import (
    INPUT_VALUE_PLACEHOLDERS,
    LOGGED_IN_MARKERS,
    LOGGED_OUT_MARKERS,
    MANUAL_JUDGMENT_PATTERN,
    STEP_INFERENCE_ACTION_PATTERN,
    STEP_INFERENCE_EXPECTED_PATTERN,
    STEP_REFERENCE_PATTERN,
    STEP_UNCERTAINTY_PATTERN,
    TITLE_ATOMICITY_VIOLATION_PATTERN,
    UI_ACTION_TYPES,
)
from app.services.case_quality.quality_scoring_service import QualityScoringService
from app.services.test_case_generation._quality_field_validators import (
    validate_title,
    validate_precondition,
    validate_expected_result,
    validate_case_category,
)
from app.services.test_case_generation._quality_step_validators import (
    validate_steps,
    validate_test_data_quality,
    validate_boundary_strategy,
    validate_type_consistency,
)

# 向后兼容别名（带下划线前缀，供 historical 导入方使用）
_LOGGED_IN_MARKERS = LOGGED_IN_MARKERS
_LOGGED_OUT_MARKERS = LOGGED_OUT_MARKERS
_INPUT_VALUE_PLACEHOLDERS = INPUT_VALUE_PLACEHOLDERS
_UI_ACTION_TYPES = UI_ACTION_TYPES
_STEP_UNCERTAINTY_PATTERN = STEP_UNCERTAINTY_PATTERN
_MANUAL_JUDGMENT_PATTERN = MANUAL_JUDGMENT_PATTERN
_STEP_REFERENCE_PATTERN = STEP_REFERENCE_PATTERN
_STEP_INFERENCE_ACTION_PATTERN = STEP_INFERENCE_ACTION_PATTERN
_STEP_INFERENCE_EXPECTED_PATTERN = STEP_INFERENCE_EXPECTED_PATTERN
_TITLE_ATOMICITY_VIOLATION = TITLE_ATOMICITY_VIOLATION_PATTERN

__all__ = [
    "validate_title", "validate_precondition", "validate_steps",
    "validate_test_data_quality", "validate_expected_result",
    "validate_case_category", "validate_boundary_strategy",
    "validate_type_consistency", "validate_single_case",
    "validate_single_case_status", "validate_cases_quality",
    "compute_quality_score", "QUALITY_MIN_SCORE",
]


def validate_single_case(case: Dict[str, Any]) -> List[str]:
    """对单条用例执行全量质量校验。

    Args:
        case: 单条测试用例字典

    Returns:
        问题描述列表，空列表表示全部通过
    """
    case_type = case.get("case_type", "")
    issues: List[str] = []
    checks: List[Tuple[str, Tuple[bool, str]]] = [
        ("标题", validate_title(case.get("title", ""))),
        ("前置条件", validate_precondition(case.get("precondition", ""))),
        ("步骤", validate_steps(case.get("steps", []), case_type=case_type)),
        ("测试数据", validate_test_data_quality(case.get("steps", []))),
        ("预期结果", validate_expected_result(case.get("expected_result", ""))),
        ("case_category", validate_case_category(case.get("case_category", ""))),
    ]
    for check_name, (passed, msg) in checks:
        if not passed:
            issues.append(f"[{check_name}] {msg}")
    # 边界值策略与类型一致性校验返回多问题列表，单独追加
    issues.extend(validate_boundary_strategy(case))
    issues.extend(validate_type_consistency(case))
    return issues


def validate_single_case_status(case: Dict[str, Any]) -> Tuple[str, List[str]]:
    """对单条用例执行全量质量校验，返回4档状态。

    状态由 QualityScoringService.grade_status 权威判定（Task 14 三合一），
    问题描述由 validate_single_case 生成（供反馈闭环描述具体问题）。
    两处共享 _classify_* 底层判定，保证状态与描述一致。

    Args:
        case: 单条测试用例字典

    Returns:
        (4档状态, 问题描述列表)
    """
    issues = validate_single_case(case)
    status = QualityScoringService.grade_status(case)
    return status, issues


def validate_cases_quality(cases: List[Dict[str, Any]], min_count: int = 0) -> Tuple[bool, List[str]]:
    """对用例列表执行全量质量校验。

    Args:
        cases: 用例字典列表
        min_count: 最少用例数要求，0 表示不校验数量

    Returns:
        (是否全部通过, 所有问题描述列表)
    """
    all_issues: List[str] = []
    if min_count > 0 and len(cases) < min_count:
        all_issues.append(f"[数量] 生成{len(cases)}条用例，要求至少{min_count}条")
    for i, case in enumerate(cases):
        case_issues = validate_single_case(case)
        for issue in case_issues:
            all_issues.append(f"用例{i + 1} {issue}")
    return len(all_issues) == 0, all_issues


def compute_quality_score(cases: List[Dict[str, Any]]) -> float:
    """计算用例列表的质量分（0~100）。

    使用7维度连续评分加权平均（Task 8）：
    标题15% + 前置条件15% + 步骤20% + 预期结果15%
    + case_category10% + action_type10% + 步骤原子性15%

    Args:
        cases: 用例字典列表

    Returns:
        质量分 0~100
    """
    if not cases:
        return 0.0
    from app.services.test_case_generation.continuous_scorer import compute_continuous_score
    scores: List[float] = [compute_continuous_score(case) for case in cases]
    return round(sum(scores) / len(scores), 1)


QUALITY_MIN_SCORE = 50.0
"""质量分阈值：低于此分数触发质量反馈重试"""
