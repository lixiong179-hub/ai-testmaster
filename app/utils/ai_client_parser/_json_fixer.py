import json
import re
from typing import Any, Dict, Optional
from loguru import logger


def fix_common_json_issues(json_str: str) -> Optional[str]:
    if not json_str:
        return None
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    parts = json_str.split('"')
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'//[^\n]*', '', parts[i])
    json_str = '"'.join(parts)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError as e:
        error_pos = e.pos
        context = max(0, error_pos - 50)
        logger.debug(f"JSON解析失败位置 {error_pos}: ...{json_str[context:error_pos+50]}...")
        return None


def clean_json_string(json_str: str) -> Optional[str]:
    if not json_str:
        return None
    json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', json_str)
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
    fixed = re.sub(r':("?[^",\s][^}]*?)([,{])', r': \1\2', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r'(")\s+("\w+"\s*:)', r'\1,\2', fixed)
    try:
        json.loads(fixed)
        return fixed
    except (json.JSONDecodeError, ValueError):
        pass
    fixed = re.sub(r'}(\s*{)', r'},\1', fixed)
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


def _extract_json_candidates(raw: str):
    fenced_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    for block in fenced_blocks:
        block = block.strip()
        if block:
            yield block

    stripped = raw.strip()
    if stripped:
        yield stripped

    spans = []
    for open_char, close_char in (("{", "}"), ("[", "]")):
        stack = []
        start = None
        in_string = False
        escape = False
        for index, char in enumerate(raw):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
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

    for start, end in sorted(spans, key=lambda item: (item[1] - item[0], item[0]), reverse=True):
        yield raw[start:end]


def parse_ai_json_response(raw: str) -> Optional[Any]:
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
        for value in (candidate, fix_common_json_issues(candidate), clean_json_string(candidate)):
            if not value:
                continue
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                continue
    logger.debug(f"AI JSON响应解析全部失败，原始内容: {raw[:200]}")
    return None


def parse_ai_json_object(raw: str) -> Optional[Dict[str, Any]]:
    result = parse_ai_json_response(raw)
    return result if isinstance(result, dict) else None
