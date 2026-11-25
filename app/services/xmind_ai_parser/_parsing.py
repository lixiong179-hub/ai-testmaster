import json
import re
from typing import Any

from loguru import logger

from app.core.constants import DEFAULT_AI_FALLBACK_CASE_TYPE
from app.services.xmind_case_parser import XmindCaseParser


CASE_WRAPPER_KEYS: tuple[str, ...] = ("cases", "items", "data", "results")


def _strip_code_fence(text: str) -> str:
    """去掉 ```json ... ``` 围栏（含 ``` 包裹）。"""
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s*```$", "", text)


def _try_json_load(text: str) -> tuple[Any, Exception | None]:
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, exc


def _parse_embedded_json(text: str) -> Any | None:
    """从含散文的响应中抠出 JSON：原文 → 修复版 → 残片抽取（三级退化）。"""
    json_match = re.search(r"[{\[].*[}\]]", text, re.DOTALL)
    if not json_match:
        logger.warning("AI 响应中未找到 JSON")
        return None
    json_text = json_match.group()

    parsed, _ = _try_json_load(json_text)
    if parsed is not None:
        return parsed

    repaired_text = _repair_json_text(json_text)
    parsed, repaired_exc = _try_json_load(repaired_text)
    if parsed is not None:
        return parsed

    logger.warning(f"AI 响应 JSON 解析失败: {repaired_exc}")
    return _extract_case_objects(repaired_text) or None


def _unwrap_case_list(parsed: Any) -> Any:
    """dict 包装（cases/items/data/results）→ 内层 list。"""
    if not isinstance(parsed, dict):
        return parsed
    for key in CASE_WRAPPER_KEYS:
        if isinstance(parsed.get(key), list):
            return parsed[key]
    return parsed


def _parse_ai_response(text: str, expected_count: int) -> list[dict[str, Any]] | None:
    text = text.strip()
    if not text:
        logger.warning("AI 响应内容为空")
        return None

    parsed, _ = _try_json_load(_strip_code_fence(text))
    if parsed is None:
        parsed = _parse_embedded_json(text)
    if parsed is None:
        return None

    parsed = _unwrap_case_list(parsed)
    if not isinstance(parsed, list):
        logger.warning("AI 响应无法提取为数组")
        return None

    if len(parsed) != expected_count:
        logger.warning(f"AI 返回 {len(parsed)} 条，期望 {expected_count} 条")

    return parsed


def _repair_json_text(text: str) -> str:
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    text = re.sub(r"}\s*{", "},{", text)
    text = re.sub(r"]\s*{", "],{", text)
    text = re.sub(r"}\s*\[", "},[", text)
    text = re.sub(r'([}\]"])\s*\n\s*("[^"\n]+"\s*:)', r"\1,\2", text)
    return text


def _extract_case_objects(text: str) -> list[dict[str, Any]]:
    cases_match = re.search(r'"cases"\s*:\s*\[', text)
    if cases_match:
        start = cases_match.end()
        end = text.rfind("]")
        source = text[start : end if end > start else len(text)]
    else:
        array_start = text.find("[")
        array_end = text.rfind("]")
        if array_start == -1:
            source = text
        else:
            source = text[array_start + 1 : array_end if array_end > array_start else len(text)]

    decoder = json.JSONDecoder()
    results: list[dict[str, Any]] = []
    index = 0
    while index < len(source):
        object_start = source.find("{", index)
        if object_start == -1:
            break
        try:
            parsed, offset = decoder.raw_decode(source[object_start:])
        except json.JSONDecodeError:
            index = object_start + 1
            continue
        if isinstance(parsed, dict):
            results.append(parsed)
        index = object_start + offset
    return results


def _normalize_case(raw: dict[str, Any], fallback_module: str) -> dict[str, Any]:
    module = raw.get("module", fallback_module) or fallback_module
    precondition = raw.get("precondition", "")
    title = raw.get("title", "")[: XmindCaseParser.TITLE_MAX_LEN]
    expected_result = raw.get("expected_result", "")
    priority = raw.get("priority", 2)
    if priority not in (1, 2, 3):
        priority = 2

    raw_steps = raw.get("steps", [])
    steps: list[dict[str, Any]] = []
    for idx, step in enumerate(raw_steps, 1):
        if isinstance(step, dict):
            steps.append(
                {
                    "step": idx,
                    "action": step.get("action", ""),
                    "expected_result": step.get("expected_result", ""),
                    "param": "",
                }
            )

    if not steps and expected_result:
        steps = [
            {
                "step": 1,
                "action": f"检查并确认：{title}",
                "expected_result": expected_result,
                "param": "",
            }
        ]

    actions = [s["action"] for s in steps if s["action"]]

    point = (
        title[: XmindCaseParser.POINT_MAX_LEN]
        if title
        else (actions[0][: XmindCaseParser.POINT_MAX_LEN] if actions else "")
    )

    return {
        "module": module[: XmindCaseParser.MODULE_MAX_LEN],
        "function": "",
        "title": title,
        "point": point,
        "precondition": precondition,
        "steps": steps,
        "expected_result": expected_result,
        "priority": priority,
        "case_type": raw.get("case_type", DEFAULT_AI_FALLBACK_CASE_TYPE) or DEFAULT_AI_FALLBACK_CASE_TYPE,
        "source_depth": 0,
        "action_count": len(actions),
        "expected_count": 1 if expected_result else 0,
        "condition_count": len(precondition.split("\n")) if precondition else 0,
        "ignored_count": 0,
    }
