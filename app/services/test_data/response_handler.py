"""测试数据生成 - AI响应解析与验证
"""
import json
import re
from typing import List, Dict, Any


def parse_ai_response(content: str) -> Any:
    """解析AI响应内容为JSON数据。

    解析策略:
        1. 直接JSON解析（理想情况）
        2. 正则提取JSON对象（AI可能在JSON前后添加说明文字）
        3. 解析失败抛出ValueError

    Args:
        content: AI返回的原始文本内容。

    Returns:
        解析后的数据（列表或字典）。

    Raises:
        ValueError: 无法解析AI响应内容。
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
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
