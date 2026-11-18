import re
from typing import Any

from app.utils.ai_client_parser import (
    extract_input_value_from_expected,
    infer_action_type,
    infer_test_category,
)

#: 旧版 `case_type` 字面量：命中即视为「需要重新推断」。
_LEGACY_CASE_TYPES = (
    "功能测试",
    "功能",
    "UI",
    "API",
    "接口",
    "接口测试",
    "functional",
    "api_auto",
    "compatibility",
)
_VALID_CASE_TYPES = ("ui_automation", "manual", "api_automation", "performance", "security")
_PRIORITY_MAP = {1: "P0", 2: "P2", 3: "P3"}


def _add_step_number(text: str, idx: int) -> str:
    """给预期结果补「N. 」序号；已有序号或已是【】/[] 标记则原样返回。"""
    stripped = text.strip()
    if (
        re.match(r"^\d+\.\s+", stripped)
        or (stripped.startswith("【") and "】" in stripped)
        or (stripped.startswith("[") and "]" in stripped)
    ):
        return stripped
    return f"{idx + 1}. {stripped}"


def _resolve_case_type_and_category(case: dict[str, Any], steps: list[dict[str, Any]]) -> tuple[str, str]:
    """归一化 `case_type` / `test_category`（旧格式两种入参共用同一判定）。"""
    case_type = case.get("case_type", "")
    test_category = case.get("test_category")
    if case_type in _LEGACY_CASE_TYPES or case_type == "" or case_type is None or not test_category:
        inferred_case_type, inferred_test_category = infer_test_category(steps)
        if case_type in _LEGACY_CASE_TYPES or case_type == "" or case_type is None:
            case_type = inferred_case_type
        if not test_category:
            test_category = inferred_test_category
    if case_type not in _VALID_CASE_TYPES:
        from app.core.constants import TestCaseType

        case_type = TestCaseType.from_legacy(case_type).value
    if test_category not in _VALID_CASE_TYPES:
        test_category = case_type
    return case_type, test_category


def _join_expected(expected_results: list[Any], steps: list[dict[str, Any]]) -> str:
    """汇总整体预期：优先用 `expected_results`，否则回退到各 step 的预期。"""
    if expected_results:
        return chr(10).join([_add_step_number(r, i) for i, r in enumerate(expected_results)])
    return chr(10).join(
        [_add_step_number(s.get("expected_result", ""), i) for i, s in enumerate(steps) if s.get("expected_result")]
    )


def _extract_input_from_action(action_text: str) -> str:
    """从动作描述里抠出「输入/填写 "xxx"」或「选择 "xxx"」的值。"""
    match = re.search(r"(?:输入|填写)[：:]?\s*['\"']([^'\"]+)['\"']", action_text)
    if not match:
        match = re.search(r"选择\s*['\"']([^'\"]+)['\"']", action_text)
    return match.group(1) if match else ""


def _normalize_new_step(step: dict[str, Any], idx: int, expected_result: str) -> dict[str, Any]:
    """归一化新格式的单个 step（含输入值三级回退）。"""
    action = step.get("action", "")
    action_type = step.get("action_type", "") or infer_action_type(action)
    input_value = step.get("input_value", "")
    step_expected = step.get("expected_result", "")
    if not expected_result and step_expected:
        expected_result = step_expected
    if action_type == "input" and not input_value:
        extracted, cleaned = extract_input_value_from_expected(expected_result)
        if extracted:
            input_value = extracted
            expected_result = cleaned
    if not input_value and action_type in ("input", "select"):
        input_value = _extract_input_from_action(action)
    return {
        "step": step.get("step", str(idx + 1)),
        "action": action,
        "action_type": action_type,
        "input_value": input_value,
        "target_element": step.get("target_element", ""),
        "description": step.get("description") or f"{step.get('step', idx + 1)}. {action}",
        "expected_result": expected_result,
        "test_data": step.get("test_data", []),
        "ui_elements": step.get("ui_elements", []),
    }


def _extract_target_element(action: str) -> str:
    """从动作描述里取首个引号包裹的目标元素名。"""
    elem_match = re.search(r"[\"“](.+?)[\"”]", action)
    return elem_match.group(1).strip() if elem_match else ""


def _normalize_old_step(step: dict[str, Any], idx: int) -> dict[str, Any]:
    """归一化旧格式的单个 step（动作/输入值/目标元素各有独立回退）。"""
    raw_action = step.get("action", "")
    raw_description = step.get("description", "")
    action = raw_description if not raw_action and raw_description else raw_action
    action_type = infer_action_type(action)
    input_value = ""
    if action_type == "input":
        m = re.search(r"[输入填写录入键入]\s*[\"“]?(.+?)[\"”]?(?:为|：|:|$)", action)
        if m:
            input_value = m.group(1).strip()
        step_expected = step.get("expected_result", "")
        if not input_value and step_expected:
            extracted, _ = extract_input_value_from_expected(step_expected)
            if extracted:
                input_value = extracted
    return {
        "step": step.get("step", idx + 1),
        "action": action,
        "action_type": action_type,
        "input_value": input_value,
        "target_element": _extract_target_element(action),
        "description": raw_description or f"[{step.get('step', idx + 1)}] {action}",
        "expected_result": step.get("expected_result", ""),
        "test_data": step.get("test_data", []),
        "ui_elements": step.get("ui_elements", []),
    }


def normalize_new_format(case: dict[str, Any]) -> dict[str, Any]:
    steps = case.get("steps", [])
    expected_results = case.get("expected_results", [])
    normalized_steps = [
        _normalize_new_step(step, i, expected_results[i] if i < len(expected_results) else "")
        for i, step in enumerate(steps)
    ]
    overall_expected = _join_expected(expected_results, steps)
    case_type, test_category = _resolve_case_type_and_category(case, steps)
    return {
        "title": case.get("title", ""),
        "module": case.get("module", ""),
        "precondition": case.get("precondition", ""),
        "case_type": case_type,
        "test_category": test_category,
        "priority": case.get("priority", "P2"),
        "expected_result": overall_expected or case.get("expected_result", ""),
        "test_data": case.get("test_data", {}),
        "steps": normalized_steps,
        "change_type": case.get("change_type", "added"),
        "parent_case_id": case.get("parent_case_id"),
        "case_category": case.get("case_category", ""),
    }


def normalize_old_format(case: dict[str, Any]) -> dict[str, Any]:
    from app.core.constants import normalize_priority

    priority_val = normalize_priority(case.get("priority", 2))
    priority_str = _PRIORITY_MAP.get(priority_val, "P2")
    raw_steps = case.get("steps", [])
    normalized_steps = [_normalize_old_step(step, i) for i, step in enumerate(raw_steps)]
    case_type, test_category = _resolve_case_type_and_category(case, raw_steps)
    return {
        "title": case.get("title", ""),
        "module": case.get("module", ""),
        "precondition": case.get("precondition", ""),
        "case_type": case_type,
        "test_category": test_category,
        "priority": priority_str,
        "expected_result": case.get("expected_result", ""),
        "test_data": case.get("test_data", {}),
        "steps": normalized_steps,
        "change_type": case.get("change_type", "added"),
        "parent_case_id": case.get("parent_case_id"),
        "case_category": case.get("case_category", ""),
    }
