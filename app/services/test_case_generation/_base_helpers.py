"""test_case_generation 基础辅助函数与上下文预算控制器。

从 base_mixin.py 拆分而来，包含模块级纯函数和 ContextBudgetController，
供 TestCaseGenerationBaseMixin 及其子类使用。

业务原因：base_mixin.py 单文件超过 350 行限制，按职责拆分模块级辅助
函数到独立文件，使主 mixin 文件聚焦于业务流程编排。
"""
import json
import re
from typing import Any, Dict, List, Optional

from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen
from app.services.test_case_generation.test_point_loader import (
    _extract_function_from_ai_prompt,
)


# 测试点分页与上下文预算默认值
DEFAULT_CONTEXT_TOKEN_BUDGET = 5000
DEFAULT_MATCHED_REQUIREMENT_LIMIT = 3
DEFAULT_MATCHED_UI_SCREEN_LIMIT = 3
DEFAULT_ADJACENT_UI_SCREEN_LIMIT = 2

# UI 元素关键词提示：检测需求描述中提到的关键 UI 元素
REQUIRED_UI_ELEMENT_HINTS = (
    "忘记密码",
    "验证码",
    "提交",
    "下一步",
    "上一步",
    "登录",
    "注册",
    "搜索",
    "支付",
    "结算",
    "加入购物车",
    "保存",
    "取消",
    "确认",
)

# 需求文档操作动词集合，用于判定需求描述是否具备可执行的操作意图
REQUIREMENT_ACTION_VERBS = (
    "点击", "输入", "提交", "选择", "查看", "验证", "确认", "核对",
    "观察", "获取", "填写", "勾选", "切换", "按下", "长按", "等待",
    "打开", "进入", "返回",
)
REQUIREMENT_MIN_CHAR_COUNT = 50


def _dedupe_ints(values: Optional[List[int]]) -> List[int]:
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


def _safe_json_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _extract_terms(*parts: Any) -> set[str]:
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
    if not terms:
        return 0
    text = " ".join(_safe_json_text(part) for part in parts).lower()
    return sum(1 for term in terms if term and term in text)


def _warning(code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": detail or {}}


def _assess_requirement_quality(
    requirement_text: str,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """评估需求文档质量等级，并给出对应警告。

    质量等级判定规则:
        - insufficient: 文本过短（字数 < REQUIREMENT_MIN_CHAR_COUNT）
        - vague: 文本足够长但缺乏操作动词，AI 应保守生成可执行步骤
        - sufficient: 文本足够长且包含操作动词

    边界场景:
        - 空字符串或 None 入参归为 insufficient，避免下游对空需求做激进生成。
        - vague 仅在字数达标且无任何操作动词时触发，提示 AI 保守生成。

    Args:
        requirement_text: 已聚合的需求文档文本（调用方负责 strip）。

    Returns:
        二元组 (quality, warning):
            - quality: "insufficient" / "vague" / "sufficient"
            - warning: 仅 vague 时返回 REQUIREMENT_VAGUE 警告字典；
              其余分支返回 None。insufficient 的 REQUIREMENT_TOO_SHORT
              警告由调用方按既有逻辑追加，此处不重复生成。
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


def _test_point_entry(point: TestPoint) -> Dict[str, Any]:
    return {
        "id": point.id,
        "module": point.module,
        "function": _extract_function_from_ai_prompt(point.ai_prompt),
        "point": point.point,
        "priority": point.priority,
        "requirement_id": point.requirement_id,
    }


def _test_point_search_text(points: List[TestPoint]) -> str:
    return " ".join(
        f"{point.module or ''} {point.point or ''} {point.ai_prompt or ''}"
        for point in points
    )


def _requirement_ref(requirement: Requirement) -> Dict[str, Any]:
    return {
        "id": requirement.id,
        "req_no": requirement.req_no,
        "title": requirement.title,
        "status": requirement.status,
        "source_file_id": requirement.source_file_id,
    }


def _screen_ref(screen: UIPrototypeScreen, confidence: str) -> Dict[str, Any]:
    return {
        "id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "confidence": confidence,
        "parse_status": screen.parse_status,
        "element_count": screen.element_count or 0,
    }


def _screen_desc(screen: UIPrototypeScreen, confidence: str = "matched") -> Dict[str, Any]:
    return {
        "screen_id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "parse_status": screen.parse_status,
        "summary": screen.summary or "",
        "element_count": screen.element_count or 0,
        "button_count": screen.button_count or 0,
        "input_count": screen.input_count or 0,
        "description": screen.summary or "",
        "match_confidence": confidence,
    }


def _collect_navigation_screen_ids(screen: UIPrototypeScreen) -> List[int]:
    ids: List[int] = []

    def collect(value: Any) -> None:
        if isinstance(value, int):
            ids.append(value)
        elif isinstance(value, str):
            if value.isdigit():
                ids.append(int(value))
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"id", "screen_id", "target", "target_id", "to", "next"}:
                    collect(item)
                elif isinstance(item, (dict, list)):
                    collect(item)

    collect(screen.related_screens)
    collect(screen.navigation_flow)
    return _dedupe_ints(ids)


def _has_flow_intent(text: str) -> bool:
    keywords = ("进入", "跳转", "提交", "返回", "下一步", "上一步", "flow", "next", "submit", "back")
    lower_text = (text or "").lower()
    return any(keyword in lower_text for keyword in keywords)


def _normalize_match_text(value: Any) -> str:
    return re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", _safe_json_text(value)).lower()


def _find_missing_required_ui_terms(search_text: str, ui_specs: List[Dict[str, Any]]) -> List[str]:
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


def _dedupe_strings(values: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


class ContextBudgetController:
    """Lightweight context budget helper using a deterministic token estimate."""

    def __init__(self, max_tokens: int = DEFAULT_CONTEXT_TOKEN_BUDGET) -> None:
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(value: Any) -> int:
        text = _safe_json_text(value)
        if not text:
            return 0
        ascii_count = sum(1 for ch in text if ord(ch) < 128)
        non_ascii_count = len(text) - ascii_count
        return max(1, ascii_count // 4 + non_ascii_count // 2)

    def trim_text(self, text: str, token_budget: int) -> str:
        if not text or self.estimate_tokens(text) <= token_budget:
            return text or ""
        # Approximate two CJK chars per token. Keep the front matter because it
        # usually contains the requirement title and explicit constraints.
        char_budget = max(200, token_budget * 2)
        return text[:char_budget] + f"\n\n[上下文已按预算裁剪，原始长度 {len(text)} 字符]"


def _trim_requirement_text(
    text: str,
    terms: set[str],
    budget: ContextBudgetController,
    token_budget: int,
) -> tuple[str, bool]:
    if not text:
        return "", False
    if len(text) <= 800:
        return budget.trim_text(text, token_budget), False

    chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[。！？；;\n])\s*", text)
        if chunk and chunk.strip()
    ]
    scored_chunks = []
    for index, chunk in enumerate(chunks):
        score = _score_terms(terms, chunk)
        if score > 0:
            scored_chunks.append((score, index, chunk))

    if not scored_chunks:
        trimmed = budget.trim_text(text, token_budget)
        return trimmed, len(trimmed) < len(text)

    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    selected_indexes = set()
    for _, index, _ in scored_chunks[:4]:
        selected_indexes.add(index)
        if index > 0:
            selected_indexes.add(index - 1)
        if index + 1 < len(chunks):
            selected_indexes.add(index + 1)

    selected_text = "\n".join(chunks[index] for index in sorted(selected_indexes))
    if len(selected_text) < 500:
        selected_text = "\n".join([selected_text, text[:500]]).strip()
    trimmed = budget.trim_text(selected_text, token_budget)
    return trimmed, True


__all__ = [
    "DEFAULT_CONTEXT_TOKEN_BUDGET",
    "DEFAULT_MATCHED_REQUIREMENT_LIMIT",
    "DEFAULT_MATCHED_UI_SCREEN_LIMIT",
    "DEFAULT_ADJACENT_UI_SCREEN_LIMIT",
    "REQUIRED_UI_ELEMENT_HINTS",
    "REQUIREMENT_ACTION_VERBS",
    "REQUIREMENT_MIN_CHAR_COUNT",
    "ContextBudgetController",
    "_assess_requirement_quality",
    "_collect_navigation_screen_ids",
    "_dedupe_ints",
    "_dedupe_strings",
    "_extract_terms",
    "_find_missing_required_ui_terms",
    "_has_flow_intent",
    "_normalize_match_text",
    "_requirement_ref",
    "_safe_json_text",
    "_score_terms",
    "_screen_desc",
    "_screen_ref",
    "_test_point_entry",
    "_test_point_search_text",
    "_trim_requirement_text",
    "_warning",
]
