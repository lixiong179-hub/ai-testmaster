"""测试用例步骤级质量校验器。

从 quality_validator.py 拆分，包含步骤完整性、测试数据质量、
边界值策略与类型一致性校验。所有函数均为模块级纯函数。
"""
from typing import Any, Dict, List, Tuple

from app.services.case_quality.quality_scoring_constants import (
    CLICK_ACTION_KEYWORDS,
    INPUT_ACTION_KEYWORDS,
    INPUT_VALUE_PLACEHOLDERS,
    MANUAL_JUDGMENT_PATTERN,
    STEP_INFERENCE_ACTION_PATTERN,
    STEP_INFERENCE_EXPECTED_PATTERN,
    STEP_REFERENCE_PATTERN,
    STEP_UNCERTAINTY_PATTERN,
    UI_ACTION_TYPES,
)


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
        if STEP_REFERENCE_PATTERN.search(f"{action} {description}"):
            return False, f"第{i + 1}步引用其他步骤或用例，应写成独立可执行步骤: {action[:50]}"
        if STEP_UNCERTAINTY_PATTERN.search(action):
            return False, f"第{i + 1}步操作不确定（含\"或\"字措辞），应拆分为独立用例: {action[:50]}"
        if STEP_INFERENCE_ACTION_PATTERN.search(action):
            return False, f"第{i + 1}步操作含推断性措辞，必须基于确定事实: {action[:50]}"
        if STEP_INFERENCE_EXPECTED_PATTERN.search(expected):
            return False, f"第{i + 1}步预期结果含推断性措辞，必须可明确断言: {expected[:50]}"
        has_click = any(keyword in action for keyword in CLICK_ACTION_KEYWORDS)
        has_input = any(keyword in action for keyword in INPUT_ACTION_KEYWORDS)
        if has_click and has_input:
            return False, f"第{i + 1}步混合点击和输入操作，应拆分为多个原子步骤: {action[:50]}"
        if case_type == "ui_automation" and MANUAL_JUDGMENT_PATTERN.search(action):
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
        if not input_value or input_value in INPUT_VALUE_PLACEHOLDERS:
            action_desc = step.get("action", "")[:40]
            return False, f"第{i + 1}步action_type为{action_type}但input_value为空或占位符，应填写具体输入值 (action={action_desc})"
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
        if not input_value or input_value in INPUT_VALUE_PLACEHOLDERS:
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
        if case_type == "api_automation" and action_type in UI_ACTION_TYPES:
            issues.append(
                f"[步骤{idx}] api_automation 用例不应包含 UI 操作动作（{action_type}）"
            )

        # manual 不应含 api_call
        if case_type == "manual" and action_type == "api_call":
            issues.append(
                f"[步骤{idx}] manual 用例不应包含 api_call 动作"
            )

    return issues
