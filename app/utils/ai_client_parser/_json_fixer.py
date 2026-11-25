import json
import re
from typing import Any
from loguru import logger

# AI 误产的 JS 字符串方法调用：形如 "literal".repeat(500) / "x".padEnd(100, "0")
# 合法 JSON 值位置不会出现字符串字面量后紧跟方法调用，故此匹配专治非法 JSON
# 方法名覆盖 AI 常见的字符串生成/补齐/拼接/截取场景
_JS_STRING_METHOD_RE = re.compile(
    r'("(?:[^"\\]|\\.)*")\s*\.\s*'
    r"(?:repeat|padEnd|padStart|concat|slice|substring|substr|replace|replaceAll)"
    r"\s*\([^()]*\)",
)


def strip_js_string_methods(text: str) -> str:
    """清理 AI 误产的 JS 字符串方法调用，保留字符串字面量。

    AI 偶尔产出 "a".repeat(500) / "x".padEnd(100, "0") 这类 JS 表达式作为
    JSON 值，合法 JSON 不允许字符串字面量后跟方法调用，json.loads 必然失败。
    本函数将 "literal".method(args) 替换为 "literal"，使 JSON 可解析。
    合法 JSON 不会出现该结构（值位置字符串后应直接跟 , 或 }），故不会误伤。
    链式调用如 "a".repeat(2).repeat(3) 通过循环逐层剥离。
    """
    if '"' not in text or "." not in text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = _JS_STRING_METHOD_RE.sub(r"\1", text)
    return text


def fix_common_json_issues(json_str: str) -> str | None:
    if not json_str:
        return None
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    parts = json_str.split('"')
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"//[^\n]*", "", parts[i])
    json_str = '"'.join(parts)
    json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError as e:
        error_pos = e.pos
        context = max(0, error_pos - 50)
        logger.debug(f"JSON解析失败位置 {error_pos}: ...{json_str[context : error_pos + 50]}...")
        return None


def clean_json_string(json_str: str) -> str | None:
    if not json_str:
        return None
    json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_str)
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    fixed = re.sub(r"'([^']*)'", r'"\1"', json_str)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r':("?[^",\s][^}]*?)([,{])', r": \1\2", fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r'(")\s+("\w+"\s*:)', r"\1,\2", fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r"}(\s*{)", r"},\1", fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r'"(\w+)"\s*:\s*(?:"|)([^",}\]]+?)(\s*[},\]])', r'"\1": "\2"\3', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r'(\w+)":\s*', r'"\1": ', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    return None


class _JsonStringState:
    """括号扫描时的字符串状态机：`feed` 返回 True 表示该字符已被字符串吞掉。"""

    __slots__ = ("in_string", "escape")

    def __init__(self) -> None:
        self.in_string = False
        self.escape = False

    def feed(self, char: str) -> bool:
        if not self.in_string:
            if char == '"':
                self.in_string = True
                return True
            return False
        if self.escape:
            self.escape = False
        elif char == "\\":
            self.escape = True
        elif char == '"':
            self.in_string = False
        return True


def _scan_bracket_spans(raw: str, open_char: str, close_char: str) -> list[tuple[int, int]]:
    """扫描同层括号配对区间（跳过字符串内的括号）。"""
    spans: list[tuple[int, int]] = []
    stack: list[str] = []
    start = None
    state = _JsonStringState()
    for index, char in enumerate(raw):
        if state.feed(char):
            continue
        if char == open_char:
            if not stack:
                start = index
            stack.append(char)
        elif char == close_char and stack:
            stack.pop()
            if not stack and start is not None:
                spans.append((start, index + 1))
                start = None
    return spans


def _iter_fenced_blocks(raw: str):
    """``` 包裹的代码块内容（去空白后非空才产出）。"""
    for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE):
        text = block.strip()
        if text:
            yield text


def _extract_json_candidates(raw: str):
    """按「代码块 → 原文 → 括号区间（大者优先）」顺序产出候选串。"""
    yield from _iter_fenced_blocks(raw)

    stripped = raw.strip()
    if stripped:
        yield stripped

    spans = _scan_bracket_spans(raw, "{", "}") + _scan_bracket_spans(raw, "[", "]")
    for start, end in sorted(spans, key=lambda item: (item[1] - item[0], item[0]), reverse=True):
        yield raw[start:end]


def parse_ai_json_response(raw: str) -> Any | None:
    """4级容错解析AI响应JSON。

    解析策略:
        1. 直接 json.loads
        2. fix_common_json_issues（移除注释、尾逗号，保护引号内URL）
        3. clean_json_string（修复单引号、控制字符、缺失引号等）
        4. 从代码块或文本中提取完整 JSON 对象/数组后重试

    Args:
        raw: AI返回的原始文本

    Returns:
        解析成功的 JSON 值（通常是 dict 或 list），或 None
    """
    if not raw or not raw.strip():
        return None

    seen = set()
    for candidate in _extract_json_candidates(raw):
        if candidate in seen:
            continue
        seen.add(candidate)
        # JS 表达式剥离放在常规修复之后，并叠加 fix/clean 组合以应对
        # "a".repeat(500) + 尾逗号 + 单引号等复合非法情形
        js_stripped = strip_js_string_methods(candidate)
        for value in (
            candidate,
            fix_common_json_issues(candidate),
            clean_json_string(candidate),
            js_stripped,
            fix_common_json_issues(js_stripped),
            clean_json_string(js_stripped),
        ):
            if not value:
                continue
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                continue
    logger.debug(f"AI JSON响应解析全部失败，原始内容: {raw[:200]}")
    return None


def parse_ai_json_object(raw: str) -> dict[str, Any] | None:
    result = parse_ai_json_response(raw)
    return result if isinstance(result, dict) else None
