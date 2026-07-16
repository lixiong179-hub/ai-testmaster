"""test_case_generation 上下文预算控制器与需求文本裁剪。

基于确定性 token 估算的预算控制，并按关键词相关性裁剪需求文本，
保留高分段落及相邻上下文。
"""
import re
from typing import Any, Tuple

from app.services.test_case_generation._helpers_constants import DEFAULT_CONTEXT_TOKEN_BUDGET
from app.services.test_case_generation._helpers_text import _safe_json_text, _score_terms


# ── 上下文预算控制器 ──
class ContextBudgetController:
    """基于确定性 token 估算的上下文预算控制器。"""

    def __init__(self, max_tokens: int = DEFAULT_CONTEXT_TOKEN_BUDGET) -> None:
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(value: Any) -> int:
        """估算文本 token 数（ASCII 4字符/token，非 ASCII 2字符/token）。"""
        text = _safe_json_text(value)
        if not text:
            return 0
        ascii_count = sum(1 for ch in text if ord(ch) < 128)
        non_ascii_count = len(text) - ascii_count
        return max(1, ascii_count // 4 + non_ascii_count // 2)

    def trim_text(self, text: str, token_budget: int) -> str:
        """按 token 预算裁剪文本，保留前部（含标题与约束）。"""
        if not text or self.estimate_tokens(text) <= token_budget:
            return text or ""
        char_budget = max(200, token_budget * 2)
        return text[:char_budget] + f"\n\n[上下文已按预算裁剪，原始长度 {len(text)} 字符]"


def _trim_requirement_text(
    text: str,
    terms: set[str],
    budget: ContextBudgetController,
    token_budget: int,
) -> Tuple[str, bool]:
    """按关键词相关性裁剪需求文本，保留高分段落及相邻上下文。"""
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
