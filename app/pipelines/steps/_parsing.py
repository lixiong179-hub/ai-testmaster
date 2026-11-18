import json
import re
from typing import Any

from loguru import logger


#: `json.loads` 失败哨兵——用于区分「解析失败」与「合法 JSON 的 null」。
_JSON_PARSE_FAILED = object()


def _strip_code_fence(text: str) -> str:
    """去掉首尾空白与 ``` 代码围栏（含围栏无结尾的容错）。"""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    return "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])


def _loads_or_sentinel(text: str) -> Any:
    """解析 JSON；失败返回 `_JSON_PARSE_FAILED`（不抛异常，便于链式回退）。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _JSON_PARSE_FAILED


def _normalize_cases(payload: Any, *, allow_cases_key: bool) -> list[dict[str, Any]] | None:
    """把已解析的 JSON 归一化为用例列表；无法归一化返回 None。

    `allow_cases_key=True` 走「`cases` / `test_cases` 包装」路径（首轮与修复后解析用）；
    `False` 用于 `clean_json_string` 路径，该路径历史上只认顶层 list 或含 title/steps 的 dict。
    """
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    if allow_cases_key:
        cases = payload.get("cases") or payload.get("test_cases") or []
        if isinstance(cases, list):
            return cases
    if payload.get("title") or payload.get("steps"):
        return [payload]
    return None


def _parse_from_array_fragment(text: str) -> Any | None:
    """末级兜底：正则截取首个 `[...]` 片段，清洗后解析（不校验顶层类型，与历史行为一致）。"""
    from app.utils.ai_client_parser import clean_json_string

    json_match = re.search(r"\[[\s\S]*\]", text)
    if not json_match:
        return None
    fixed_array = clean_json_string(json_match.group())
    if not fixed_array:
        return None
    payload = _loads_or_sentinel(fixed_array)
    return None if payload is _JSON_PARSE_FAILED else payload


def _parse_case_response(content: str) -> list[dict[str, Any]] | None:
    """AI 响应 → 用例列表，按「原文 / 修复后 / 清洗后 / 正则截取」四级回退。"""
    from app.utils.ai_client_parser import clean_json_string, fix_common_json_issues

    text = _strip_code_fence(content)

    for candidate in (text, fix_common_json_issues(text)):
        if not candidate:
            continue
        payload = _loads_or_sentinel(candidate)
        if payload is _JSON_PARSE_FAILED:
            continue
        cases = _normalize_cases(payload, allow_cases_key=True)
        if cases is not None:
            return cases

    cleaned = clean_json_string(text)
    if cleaned:
        payload = _loads_or_sentinel(cleaned)
        if payload is not _JSON_PARSE_FAILED:
            cases = _normalize_cases(payload, allow_cases_key=False)
            if cases is not None:
                return cases

    return _parse_from_array_fragment(text)


def _validate_test_data(case: dict[str, Any]) -> None:
    if "test_data" not in case:
        case["test_data"] = {}
        return

    td = case["test_data"]
    if not isinstance(td, dict):
        logger.warning(
            "test_data 类型非法 ({}), 使用空对象兜底, title={}",
            type(td).__name__,
            case.get("title", "")[:30],
        )
        case["test_data"] = {}
        return

    valid_keys = {"normal", "boundary", "abnormal"}
    has_valid_key = any(k in valid_keys for k in td)
    if not has_valid_key and len(td) > 0:
        logger.warning(
            "test_data 缺少 normal/boundary/abnormal 键, 保留原值, title={}",
            case.get("title", "")[:30],
        )

    for key in list(td.keys()):
        if not isinstance(td[key], dict):
            logger.warning(
                "test_data['{}'] 非dict类型，已重置, title={}",
                key,
                case.get("title", "")[:30],
            )
            td[key] = {}


def _enrich_case_data(parsed: list[dict[str, Any]], tp: dict[str, Any], has_ui: bool) -> list[dict[str, Any]]:
    tp_module = tp.get("module", "")
    tp_point = tp.get("point", "")
    tp_id = tp.get("id")

    for case in parsed:
        if not case.get("module"):
            case["module"] = tp_module
        if not case.get("title"):
            case["title"] = f"{tp_point} - 测试用例"
        case["test_point_id"] = tp_id
        case["lifecycle_status"] = "draft"
        if not case.get("case_type"):
            case["case_type"] = "api_automation" if not has_ui else "ui_automation"
        _validate_test_data(case)

    _fill_depends_on(parsed)

    return parsed


def _fill_depends_on(parsed: list[dict[str, Any]]) -> None:
    """根据 case_category 自动填充 depends_on 和 anchor_step。

    对于 boundary/exception 类型的用例，自动关联到同组的 positive 用例，
    并根据标题关键词推断 anchor_step（分支/异常触发点的主干步骤号）。
    如果 AI 已填写 depends_on/anchor_step 则保留原值。
    """
    positive_cases = [c for c in parsed if c.get("case_category") == "positive"]
    if not positive_cases:
        return

    main_title = positive_cases[0].get("title", "")
    main_steps = positive_cases[0].get("steps", [])

    for case in parsed:
        if case.get("case_category") in ("boundary", "exception"):
            if case.get("depends_on"):
                continue
            case["depends_on"] = main_title
            if not case.get("anchor_step") and main_steps:
                case["anchor_step"] = _infer_anchor_step(case, main_steps)
            if not case.get("fallback_steps") and main_steps:
                anchor = case.get("anchor_step")
                if anchor is not None:
                    case["fallback_steps"] = _build_fallback_steps(main_steps, anchor)


def _infer_anchor_step(case: dict[str, Any], main_steps: list[dict[str, Any]]) -> int | None:
    """根据分支/异常用例的前置条件和标题推断 anchor_step。

    匹配策略：
    1. 从前置条件中提取页面名称（如"已处于确认订单页"→"确认订单"）
    2. 在主干步骤的预期结果中查找跳转到该页面的步骤
    3. 回退：在前置条件中查找主干步骤操作关键词
    """
    precond = case.get("precondition", "")
    title = case.get("title", "")

    page_name = _extract_page_name(precond)
    if page_name:
        for idx, step in enumerate(main_steps):
            expected = (step.get("expected_result", "") or "").lower()
            action = (step.get("action", "") or step.get("description", "")).lower()
            if page_name in expected or page_name in action:
                step_num = step.get("step") or step.get("step_number") or (idx + 1)
                try:
                    return int(step_num)
                except (ValueError, TypeError):
                    return idx + 1

    action_keywords = _extract_action_keywords(title + " " + precond)
    if action_keywords:
        best_step = None
        best_score = 0
        for idx, step in enumerate(main_steps):
            step_text = (
                (step.get("action", "") or step.get("description", "")) + " " + (step.get("expected_result", "") or "")
            ).lower()
            score = sum(1 for kw in action_keywords if kw in step_text)
            if score > best_score:
                best_score = score
                step_num = step.get("step") or step.get("step_number") or (idx + 1)
                try:
                    best_step = int(step_num)
                except (ValueError, TypeError):
                    best_step = idx + 1
        if best_step is not None:
            return best_step

    return None


def _extract_page_name(precond: str) -> str | None:
    """从前置条件中提取页面名称。

    匹配模式："已处于XX页"、"在XX页面"、"处于XX页"
    """
    import re

    patterns = [
        r"已处于(.+?页)",
        r"处于(.+?页)",
        r"在(.+?页面)",
        r"在(.+?页)",
    ]
    for pattern in patterns:
        m = re.search(pattern, precond)
        if m:
            return m.group(1).replace("页面", "页")
    return None


def _extract_action_keywords(text: str) -> list[str]:
    """从文本中提取操作关键词用于匹配。"""
    keywords = []
    for kw in [
        "提交订单",
        "确认支付",
        "立即购买",
        "使用优惠券",
        "点击购买",
        "点击提交",
        "点击支付",
        "支付失败",
        "库存不足",
        "登录",
        "注册",
    ]:
        if kw in text:
            keywords.append(kw)
    return keywords


def _build_fallback_steps(main_steps: list[dict[str, Any]], anchor_step: int) -> list[dict[str, Any]]:
    """从主干用例步骤中提取到 anchor_step 为止的导航步骤子集。

    作为快照不可用时的降级方案，执行引擎可以用这些步骤
    自行导航到目标页面，而不依赖主干快照恢复。

    Args:
        main_steps: 主干用例的完整步骤列表。
        anchor_step: 锚点步骤号，提取步骤1到anchor_step。

    Returns:
        精简的导航步骤列表。
    """
    fallback = []
    for step in main_steps:
        step_num = step.get("step") or step.get("step_number")
        if step_num is None:
            continue
        try:
            num = int(step_num)
        except (ValueError, TypeError):
            continue
        if num > anchor_step:
            break
        fallback.append(
            {
                "step": num,
                "action": step.get("action", "") or step.get("description", ""),
                "action_type": step.get("action_type", "click"),
                "target_element": step.get("target_element", ""),
                "input_value": step.get("input_value", ""),
            }
        )
    return fallback


def _enrich_case_data_with_task(
    parsed: list[dict[str, Any]],
    task: dict[str, Any],
    has_ui: bool,
) -> list[dict[str, Any]]:
    tp_module = task.get("candidate_module", task.get("module", ""))
    tp_point = task.get("candidate_description", "") or task.get("modification_hint", "")
    task_id = task.get("task_id")
    task_type = task.get("task_type", "")
    case_id = task.get("case_id")

    for case in parsed:
        if not case.get("module"):
            case["module"] = tp_module
        if not case.get("title"):
            case["title"] = f"{tp_point} - 测试用例"
        case["task_id"] = task_id
        case["lifecycle_status"] = "draft"
        if not case.get("case_type"):
            case["case_type"] = "api_automation" if not has_ui else "ui_automation"
        _validate_test_data(case)
        if task_type == "modify":
            case["ai_change_type"] = "modified"
            case["parent_case_id"] = case_id
        elif task_type == "locator_fix":
            case["ai_change_type"] = "locator_fix"
            case["parent_case_id"] = case_id
        elif task_type == "create":
            case["ai_change_type"] = "added"

    _fill_depends_on(parsed)

    return parsed
