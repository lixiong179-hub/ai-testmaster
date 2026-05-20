"""测试用例AI生成 - 响应解析工具
"""
import json
import re
from typing import Dict, Any, List


def _repair_truncated_json(text: str) -> str:
    """尝试修复被截断的JSON字符串。

    策略：
    1. 找到最后一个完整的对象/数组结束位置
    2. 补全缺失的括号
    """
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False
    last_valid_obj_end = -1
    last_valid_arr_end = -1

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
            if open_braces == 0:
                last_valid_obj_end = i
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1
            if open_brackets == 0:
                last_valid_arr_end = i

    if last_valid_arr_end > 0:
        return text[:last_valid_arr_end + 1]

    if last_valid_obj_end > 0:
        return text[:last_valid_obj_end + 1]

    repaired = text
    if open_brackets > 0:
        repaired += ']' * open_brackets
    if open_braces > 0:
        repaired += '}' * open_braces
    return repaired


def _strip_code_block(text: str) -> str:
    """移除markdown代码块标记。"""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    return text.strip()


def parse_ai_response(content: str) -> Dict[str, Any]:
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

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return {"cases": result}
        if isinstance(result, dict):
            return result
        raise ValueError(f"AI响应解析为非对象/数组类型: {type(result)}")
    except (json.JSONDecodeError, ValueError):
        pass

    json_match = re.search(r'\[[\s\S]*\]', cleaned)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            if isinstance(result, list):
                return {"cases": result}
        except json.JSONDecodeError:
            try:
                repaired = _repair_truncated_json(json_match.group(0))
                result = json.loads(repaired)
                if isinstance(result, list):
                    return {"cases": result}
            except (json.JSONDecodeError, ValueError):
                pass

    json_match = re.search(r'\{[\s\S]*\}', cleaned)
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            try:
                repaired = _repair_truncated_json(json_match.group(0))
                result = json.loads(repaired)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

    try:
        repaired = _repair_truncated_json(cleaned)
        result = json.loads(repaired)
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            return {"cases": result}
    except (json.JSONDecodeError, ValueError):
        pass

    raise ValueError("无法解析AI响应内容")
