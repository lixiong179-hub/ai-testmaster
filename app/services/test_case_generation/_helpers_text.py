"""test_case_generation 文本/JSON 处理、去重工具与需求质量评估。

提供模块级纯函数：JSON 文本化、搜索词提取与打分、文本归一化、
整数/字符串去重保序、需求质量等级评估、流程意图检测、UI 元素覆盖检查。
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.test_case_generation._helpers_constants import (
    REQUIRED_UI_ELEMENT_HINTS,
    REQUIREMENT_ACTION_VERBS,
    REQUIREMENT_MIN_CHAR_COUNT,
)


# ── 文本处理与需求质量评估 ──
def _safe_json_text(value: Any) -> str:
    """将任意值转为字符串，dict/list 转 JSON 字符串。"""
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _extract_function_from_ai_prompt(ai_prompt: Optional[str]) -> str:
    """从 ai_prompt JSON 字符串提取 function 字段，失败返回空串。"""
    if not ai_prompt:
        return ""
    try:
        data = json.loads(ai_prompt)
        if isinstance(data, dict):
            return str(data.get('function', '') or '')
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return ""


def _extract_terms(*parts: Any) -> set[str]:
    """从多个文本片段提取搜索词集合（中文按 2-gram，英文按 token）。"""
    text = " ".join(str(part or "") for part in parts).lower()
    raw_tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    terms: set[str] = set()
    for token in raw_tokens:
        if len(token) < 2:
            continue
        terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
            terms.update(token[i:i + 2] for i in range(len(token) - 1))
    return {term for term in terms if len(term) >= 2}


def _score_terms(terms: set[str], *parts: Any) -> int:
    """计算 terms 在 parts 文本中的命中数。"""
    if not terms:
        return 0
    text = " ".join(_safe_json_text(part) for part in parts).lower()
    return sum(1 for term in terms if term and term in text)


def _warning(code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构造警告字典。"""
    return {"code": code, "message": message, "detail": detail or {}}


def _dedupe_ints(values: List[int]) -> List[int]:
    """整数去重保序。"""
    if not values:
        return []
    result: List[int] = []
    seen = set()
    for value in values:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _dedupe_strings(values: List[str]) -> List[str]:
    """字符串去重保序，过滤空值。"""
    result: List[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _assess_requirement_quality(
    requirement_text: str,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """评估需求文档质量等级并给出警告。

    质量等级：
        - insufficient: 文本过短（< REQUIREMENT_MIN_CHAR_COUNT）
        - vague: 文本足够长但缺乏操作动词
        - sufficient: 文本足够长且包含操作动词
    """
    text = requirement_text or ""
    char_count = len(text)
    has_action_verb = any(verb in text for verb in REQUIREMENT_ACTION_VERBS)
    if char_count < REQUIREMENT_MIN_CHAR_COUNT:
        return ("insufficient", None)
    if not has_action_verb:
        return (
            "vague",
            {
                "code": "REQUIREMENT_VAGUE",
                "severity": "medium",
                "message": "需求文档有内容但缺乏操作动词，请保守生成可执行步骤",
            },
        )
    return ("sufficient", None)


def _has_flow_intent(text: str) -> bool:
    """检测文本是否包含流程跳转意图。"""
    keywords = ("进入", "跳转", "提交", "返回", "下一步", "上一步", "flow", "next", "submit", "back")
    lower_text = (text or "").lower()
    return any(keyword in lower_text for keyword in keywords)


def _normalize_match_text(value: Any) -> str:
    """归一化文本用于匹配：移除标点空白并小写。"""
    return re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", _safe_json_text(value)).lower()


def _find_missing_required_ui_terms(search_text: str, ui_specs: List[Dict[str, Any]]) -> List[str]:
    """检查 UI 元素是否覆盖测试点所需关键词，返回缺失词列表。"""
    if not search_text or not ui_specs:
        return []
    required_terms = [
        term for term in REQUIRED_UI_ELEMENT_HINTS
        if term.lower() in search_text.lower()
    ]
    if not required_terms:
        return []

    ui_text = _normalize_match_text([
        item.get("ui_spec")
        for item in ui_specs
        if isinstance(item, dict)
    ])
    missing = [
        term for term in required_terms
        if _normalize_match_text(term) not in ui_text
    ]
    return _dedupe_strings(missing)
