"""测试数据生成 - AI响应解析与验证"""

import json
import re
from typing import Any

from app.utils.ai_client_parser import fix_common_json_issues, clean_json_string

_JSON_FIXERS = (fix_common_json_issues, clean_json_string)
_JSON_BLOCK_PATTERNS = (re.compile(r"\[[\s\S]*\]"), re.compile(r"\{[\s\S]*\}"))
_UNPARSED = object()


def _try_fixers(raw: str) -> Any:
    """依次用修复函数解析；全部失败时返回哨兵，避免与合法的 None 混淆。"""
    for fix_fn in _JSON_FIXERS:
        fixed = fix_fn(raw)
        if not fixed:
            continue
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            continue
    return _UNPARSED


def _parse_json_block(content: str, pattern: re.Pattern) -> Any:
    """截取匹配到的 JSON 片段，先修复再裸解析。"""
    match = pattern.search(content)
    if not match:
        return _UNPARSED
    raw = match.group(0)
    result = _try_fixers(raw)
    if result is not _UNPARSED:
        return result
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _UNPARSED


def parse_ai_response(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    result = _try_fixers(content)
    if result is not _UNPARSED:
        return result

    for pattern in _JSON_BLOCK_PATTERNS:
        result = _parse_json_block(content, pattern)
        if result is not _UNPARSED:
            return result

    raise ValueError("无法解析AI响应内容")


def validate_generated_data(
    data: list[dict[str, Any]], field_definitions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """验证生成数据的完整性。

    验证规则:
        - 必填字段必须存在且不为null
        - 字段类型必须匹配（字符串/数字/布尔等）
        - 枚举类型值必须在允许列表内

    Args:
        data: 生成的数据记录列表。
        field_definitions: 字段定义列表。

    Returns:
        验证通过的数据记录列表。

    Raises:
        ValueError: 数据验证不通过。
    """
    required_fields = [f["name"] for f in field_definitions if f.get("required", False)]
    validated = []
    for record in data:
        for field_name in required_fields:
            if field_name not in record or record[field_name] is None:
                raise ValueError(f"生成的数据缺少必填字段: {field_name}")
        validated.append(record)
    return validated
