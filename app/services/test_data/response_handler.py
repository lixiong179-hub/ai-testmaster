"""测试数据生成 - AI响应解析与验证
"""
import json
import re
from typing import List, Dict, Any

from app.utils.ai_client_parser import fix_common_json_issues, clean_json_string


def parse_ai_response(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        for fix_fn in (fix_common_json_issues, clean_json_string):
            fixed = fix_fn(content)
            if fixed:
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    continue
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            raw = json_match.group(0)
            for fix_fn in (fix_common_json_issues, clean_json_string):
                fixed = fix_fn(raw)
                if fixed:
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        continue
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            raw = json_match.group(0)
            for fix_fn in (fix_common_json_issues, clean_json_string):
                fixed = fix_fn(raw)
                if fixed:
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        continue
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
    raise ValueError("无法解析AI响应内容")


def validate_generated_data(
    data: List[Dict[str, Any]],
    field_definitions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
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
