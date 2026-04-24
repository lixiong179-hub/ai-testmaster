"""测试数据生成 - Prompt构建逻辑
"""
import json
from typing import List, Dict, Any, Optional


def build_generation_prompt(
    field_definitions: List[Dict[str, Any]],
    count: int,
    context: Optional[str],
    data_type: str
) -> str:
    """构建数据生成的结构化Prompt。

    Prompt结构:
        1. 角色设定（测试数据专家）
        2. 数据类型说明（normal/boundary/invalid/special）
        3. 字段定义列表（JSON格式）
        4. 业务上下文（可选）
        5. 输出格式要求（JSON数组）

    Args:
        field_definitions: 字段定义列表。
        count: 生成记录数。
        context: 业务上下文，可选。
        data_type: 数据类型。

    Returns:
        完整的Prompt字符串。
    """
    type_descriptions = {
        "normal": "正常数据 - 符合业务规则的典型值",
        "boundary": "边界值数据 - 刚好在边界上的值（如最大值、最小值、空值）",
        "invalid": "无效数据 - 不符合业务规则的数据（如格式错误、超长字符串）",
        "special": "特殊字符数据 - 包含特殊字符的数据（如SQL注入字符、XSS字符）"
    }
    type_desc = type_descriptions.get(data_type, "正常数据")

    fields_json = json.dumps(field_definitions, ensure_ascii=False, indent=2)

    prompt = f"""你是一名测试数据专家，请根据以下字段定义生成{count}条测试数据。

## 数据类型要求：{type_desc}

## 字段定义：
{fields_json}

## 业务上下文：
{context if context else '无特定业务上下文'}

## 输出要求：
1. 只输出JSON格式内容，不要添加任何其他文字
2. JSON必须是一个数组，每个元素是一个对象，对象的键是字段名，值是生成的数据
3. 生成的数据必须符合字段定义中的类型要求
4. 对于必填字段，必须生成值；对于非必填字段，可以生成null或省略
5. 确保生成的数据具有多样性，不要重复

## 输出JSON格式示例：
[
  {{
    "field1": "value1",
    "field2": 123,
    "field3": "2024-01-01"
  }},
  {{
    "field1": "value2",
    "field2": 456,
    "field3": "2024-02-01"
  }}
]"""
    return prompt
