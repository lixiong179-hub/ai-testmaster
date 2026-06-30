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
"""
from typing import List, Dict, Any, Tuple

from app.services.case_quality.quality_scoring_constants import (
    CLICK_ACTION_KEYWORDS,
    EXPECTED_VAGUE_WORDS,
    INPUT_ACTION_KEYWORDS,
    INPUT_VALUE_PLACEHOLDERS,
    LOGGED_IN_MARKERS,
    LOGGED_OUT_MARKERS,
    MANUAL_JUDGMENT_PATTERN,
    STEP_INFERENCE_ACTION_PATTERN,
    STEP_INFERENCE_EXPECTED_PATTERN,
    STEP_REFERENCE_PATTERN,
    STEP_UNCERTAINTY_PATTERN,
    TITLE_ATOMICITY_VIOLATION_PATTERN,
    TITLE_VAGUE_WORDS,
    UI_ACTION_TYPES,
    VALID_ACTION_TYPES,
    VALID_CASE_CATEGORIES,
)
from app.services.case_quality.quality_scoring_service import QualityScoringService

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


def validate_title(title: str) -> Tuple[bool, str]:
    """校验标题质量。

    Args:
        title: 用例标题

    Returns:
        (是否通过, 问题描述)
    """
    if not title or not title.strip():
        return False, "标题为空"
    title = title.strip()
    if len(title) < 8:
        return False, f"标题过短（{len(title)}字），需≥8字: {title}"
    if len(title) > 50:
        return False, f"标题过长（{len(title)}字），需≤50字: {title}"
    for word in TITLE_VAGUE_WORDS:
        if word in title:
            return False, f"标题包含模糊词「{word}」: {title}"
    if _TITLE_ATOMICITY_VIOLATION.search(title):
        return False, f"标题违反原子性原则（混合主流程与分支/旁路逻辑），应拆分为独立用例: {title}"
    return True, ""


def validate_precondition(precondition: str) -> Tuple[bool, str]:
    """校验前置条件完整性。

    Args:
        precondition: 前置条件文本

    Returns:
        (是否通过, 问题描述)
    """
    if not precondition or not precondition.strip():
        return False, "前置条件为空"
    precondition = precondition.strip()
    has_logged_in = any(marker in precondition for marker in _LOGGED_IN_MARKERS)
    has_logged_out = any(marker in precondition for marker in _LOGGED_OUT_MARKERS)
    if not has_logged_in and not has_logged_out:
        return False, "前置条件缺少登录状态"
    # 互斥校验：同时出现"已登录"与"未登录"标记属于语义矛盾（如"账号已登录状态为未登录"），
    # 旧实现仅用 any() 命中即放行，无法发现此类矛盾。
    if has_logged_in and has_logged_out:
        return False, "前置条件登录状态自相矛盾（同时含已登录与未登录标记）"
    if len(precondition) < 15:
        return False, f"前置条件过于简单（{len(precondition)}字）: {precondition}"
    return True, ""


def validate_steps(steps: List[Dict[str, Any]], case_type: str = "") -> Tuple[bool, str]:
    """校验步骤完整性、确定性和自动化可执行性。

    Args:
        steps: 步骤列表
        case_type: 用例类型，用于判断是否需要自动化可执行性校验

    Returns:
        (是否通过, 问题描述)
    """
    if not steps or len(steps) == 0:
        return False, "步骤列表为空"
    if len(steps) < 2:
        return False, f"步骤数不足（仅{len(steps)}步），每条用例至少需要2步（导航+核心操作），前置条件中的状态必须通过步骤到达"
    if len(steps) > 8:
        return False, f"步骤数过多（{len(steps)}步），每条用例最多8步，超过说明混合了多个测试场景，必须拆分为多条独立用例"
    for i, step in enumerate(steps):
        action = step.get("action", "") or step.get("description", "")
        description = step.get("description", "")
        if not action or not action.strip():
            return False, f"第{i + 1}步的 action 为空"
        expected = step.get("expected_result", "")
        if not expected or not expected.strip():
            return False, f"第{i + 1}步的 expected_result 为空"
        if _STEP_REFERENCE_PATTERN.search(f"{action} {description}"):
            return False, f"第{i + 1}步引用其他步骤或用例，应写成独立可执行步骤: {action[:50]}"
        if _STEP_UNCERTAINTY_PATTERN.search(action):
            return False, f"第{i + 1}步操作不确定（含\"或\"字措辞），应拆分为独立用例: {action[:50]}"
        if _STEP_INFERENCE_ACTION_PATTERN.search(action):
            return False, f"第{i + 1}步操作含推断性措辞，必须基于确定事实: {action[:50]}"
        if _STEP_INFERENCE_EXPECTED_PATTERN.search(expected):
            return False, f"第{i + 1}步预期结果含推断性措辞，必须可明确断言: {expected[:50]}"
        has_click = any(keyword in action for keyword in CLICK_ACTION_KEYWORDS)
        has_input = any(keyword in action for keyword in INPUT_ACTION_KEYWORDS)
        if has_click and has_input:
            return False, f"第{i + 1}步混合点击和输入操作，应拆分为多个原子步骤: {action[:50]}"
        if case_type == "ui_automation" and _MANUAL_JUDGMENT_PATTERN.search(action):
            return False, f"第{i + 1}步含人工判断描述，与ui_automation类型矛盾: {action[:50]}"
    return True, ""


def validate_test_data_quality(steps: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """校验测试数据质量，确保 input/select 步骤有具体输入值。

    Args:
        steps: 步骤列表

    Returns:
        (是否通过, 问题描述)
    """
    if not steps:
        return True, ""
    for i, step in enumerate(steps):
        action_type = step.get("action_type", "")
        if action_type not in ("input", "select"):
            continue
        input_value = (step.get("input_value") or "").strip()
        if not input_value or input_value in _INPUT_VALUE_PLACEHOLDERS:
            action_desc = step.get("action", "")[:40]
            return False, f"第{i + 1}步action_type为{action_type}但input_value为空或占位符，应填写具体输入值 (action={action_desc})"
    return True, ""


def validate_expected_result(expected_result: str) -> Tuple[bool, str]:
    """校验总体预期结果质量。

    检查策略：
        1. 非空且 ≥10 字
        2. 精确匹配模糊短语（如'正常显示''提交成功'）

    Args:
        expected_result: 总体预期结果文本

    Returns:
        (是否通过, 问题描述)
    """
    if not expected_result or not expected_result.strip():
        return False, "总体预期结果为空"
    expected_result = expected_result.strip()
    if len(expected_result) < 10:
        return False, f"预期结果过短（{len(expected_result)}字）: {expected_result}"
    for word in EXPECTED_VAGUE_WORDS:
        if word in expected_result:
            return False, f"预期结果包含模糊短语「{word}」: {expected_result}"
    return True, ""


def validate_case_category(case_category: str) -> Tuple[bool, str]:
    """校验 case_category 合法性。

    Args:
        case_category: 用例分类

    Returns:
        (是否通过, 问题描述)
    """
    if not case_category:
        return False, "case_category 为空"
    if case_category not in VALID_CASE_CATEGORIES:
        return False, f"case_category 非法值「{case_category}」，合法值: {sorted(VALID_CASE_CATEGORIES)}"
    return True, ""


def validate_boundary_strategy(case: Dict[str, Any]) -> List[str]:
    """校验边界用例是否使用实际边界值而非占位符。

    业务原因：case_category=boundary 的用例应使用最大值/最小值/空值/特殊字符等边界值，
    而非占位符（待输入/测试数据/xxx 等），否则边界测试无效。

    Args:
        case: 单条测试用例字典

    Returns:
        问题描述列表，空列表表示全部通过
    """
    issues: List[str] = []
    case_category = case.get("case_category", "")
    if case_category != "boundary":
        return issues

    steps = case.get("steps", [])
    if not isinstance(steps, list):
        return issues

    for idx, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            continue
        action_type = step.get("action_type", "")
        if action_type not in ("input", "select"):
            continue
        input_value = str(step.get("input_value") or "").strip()
        if not input_value or input_value in _INPUT_VALUE_PLACEHOLDERS:
            issues.append(
                f"[步骤{idx}] 边界用例应使用边界值（最大值/最小值/空值/特殊字符），"
                f"而非占位符或空值"
            )
    return issues


def validate_type_consistency(case: Dict[str, Any]) -> List[str]:
    """校验 case_type/case_category/action_type 三者组合一致性。

    业务原因：api_automation 用例不应包含 UI 操作动作（click/hover 等），
    manual 用例不应包含 api_call 动作，避免类型矛盾导致用例无法执行。

    Args:
        case: 单条测试用例字典

    Returns:
        问题描述列表，空列表表示全部通过
    """
    issues: List[str] = []
    case_type = case.get("case_type", "")
    steps = case.get("steps", [])
    if not isinstance(steps, list):
        return issues

    for idx, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            continue
        action_type = step.get("action_type", "")
        if not action_type:
            continue

        # api_automation 不应含 UI 动作
        if case_type == "api_automation" and action_type in _UI_ACTION_TYPES:
            issues.append(
                f"[步骤{idx}] api_automation 用例不应包含 UI 操作动作（{action_type}）"
            )

        # manual 不应含 api_call
        if case_type == "manual" and action_type == "api_call":
            issues.append(
                f"[步骤{idx}] manual 用例不应包含 api_call 动作"
            )

    return issues


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
