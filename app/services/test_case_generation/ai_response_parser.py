"""测试用例AI生成 - 响应解析工具"""

import json
import re
from typing import Any


class _TruncatedJsonScanner:
    """逐字符跟踪括号深度与字符串状态，用于定位最后一个完整对象/数组的结尾。

    显式建模而不是散在局部变量里，是为了让"字符串内不计数"这条规则只有一处实现。
    """

    def __init__(self) -> None:
        self.open_braces = 0
        self.open_brackets = 0
        self.in_string = False
        self.escape_next = False
        self.last_valid_obj_end = -1
        self.last_valid_arr_end = -1

    def feed(self, index: int, ch: str) -> None:
        if self.escape_next:
            self.escape_next = False
            return
        if ch == "\\" and self.in_string:
            self.escape_next = True
            return
        if ch == '"':
            self.in_string = not self.in_string
            return
        if self.in_string:
            return
        self._count_bracket(index, ch)

    def _count_bracket(self, index: int, ch: str) -> None:
        if ch == "{":
            self.open_braces += 1
        elif ch == "}":
            self.open_braces -= 1
            if self.open_braces == 0:
                self.last_valid_obj_end = index
        elif ch == "[":
            self.open_brackets += 1
        elif ch == "]":
            self.open_brackets -= 1
            if self.open_brackets == 0:
                self.last_valid_arr_end = index

    def repaired(self, text: str) -> str:
        """优先截到最后一个完整数组/对象；都找不到时补齐未闭合括号。"""
        if self.last_valid_arr_end > 0:
            return text[: self.last_valid_arr_end + 1]
        if self.last_valid_obj_end > 0:
            return text[: self.last_valid_obj_end + 1]

        repaired = text
        if self.open_brackets > 0:
            repaired += "]" * self.open_brackets
        if self.open_braces > 0:
            repaired += "}" * self.open_braces
        return repaired


def _repair_truncated_json(text: str) -> str:
    """尝试修复被截断的JSON字符串。

    策略：
    1. 找到最后一个完整的对象/数组结束位置
    2. 补全缺失的括号
    """
    scanner = _TruncatedJsonScanner()
    for index, ch in enumerate(text):
        scanner.feed(index, ch)
    return scanner.repaired(text)


def _strip_code_block(text: str) -> str:
    """移除markdown代码块标记。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _loads_with_repair(text: str):
    """先直接 loads，失败再用截断修复重试；均失败返回 None。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_repair_truncated_json(text))
    except (json.JSONDecodeError, ValueError):
        return None


def _parse_strict_json(cleaned: str) -> dict[str, Any] | None:
    """整段严格解析；数组包装为 `{"cases": [...]}`，非对象/数组返回 None。"""
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if isinstance(result, list):
        return {"cases": result}
    if isinstance(result, dict):
        return result
    return None


def _parse_embedded_object(cleaned: str) -> dict[str, Any] | None:
    """提取文本中首个 `{...}` 片段并解析（含截断修复）。"""
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if not json_match:
        return None
    parsed = _loads_with_repair(json_match.group(0))
    return parsed if isinstance(parsed, dict) else None


def _parse_embedded_array(cleaned: str) -> dict[str, Any] | None:
    """提取文本中首个 `[...]` 片段并解析（含截断修复）。"""
    json_match = re.search(r"\[[\s\S]*\]", cleaned)
    if not json_match:
        return None
    parsed = _loads_with_repair(json_match.group(0))
    return {"cases": parsed} if isinstance(parsed, list) else None


def _ordered_embedded_parsers(cleaned: str) -> tuple:
    """按 `{` / `[` 首次出现位置决定两种探测的先后顺序。"""
    first_object = cleaned.find("{")
    first_array = cleaned.find("[")
    if first_object != -1 and (first_array == -1 or first_object < first_array):
        return _parse_embedded_object, _parse_embedded_array
    return _parse_embedded_array, _parse_embedded_object


def _parse_repaired_whole(cleaned: str) -> dict[str, Any] | None:
    """整段修复后解析；对象原样返回，数组包装为 `{"cases": [...]}`。"""
    try:
        result = json.loads(_repair_truncated_json(cleaned))
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"cases": result}
    return None


def parse_ai_response(content: str) -> dict[str, Any]:
    """解析AI响应内容，支持JSON对象、JSON数组和截断JSON。

    Args:
        content: AI返回的原始文本

    Returns:
        解析后的字典，如果AI返回数组则合并为 {"cases": [...]}

    Raises:
        ValueError: 无法解析时抛出
    """
    if not content or not content.strip():
        raise ValueError("AI响应内容为空")

    cleaned = _strip_code_block(content)

    parsed = _parse_strict_json(cleaned)
    if parsed is not None:
        return parsed

    for parser in _ordered_embedded_parsers(cleaned):
        parsed = parser(cleaned)
        if parsed is not None:
            return parsed

    parsed = _parse_repaired_whole(cleaned)
    if parsed is not None:
        return parsed

    raise ValueError("无法解析AI响应内容")
