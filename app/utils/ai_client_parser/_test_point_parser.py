import json
import re
from typing import Any

from loguru import logger

from app.utils.ai_client_parser._json_fixer import clean_json_string

#: fallback 处理的输入上限（超长内容截断，避免正则回溯爆炸）。
_MAX_CONTENT_LENGTH = 50000

#: 数组内的「扁平/一层嵌套」对象形态。
_OBJECT_PATTERN = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"

#: 直接抓 `"point": "..."` 值（允许内部出现少量引号）。
_POINT_PATTERN = r'"point"\s*:\s*"([^"]*(?:[^"]|"{2}){0,5}?)"'

#: 可用于识别「宽松对象」的键名。
_LOOSE_KEY_PATTERN = r'"(?:module|function|point|priority)"\s*:\s*'


def _is_test_point(obj: Any) -> bool:
    """是否为有效测试点：dict 且 `point` 非空。"""
    return isinstance(obj, dict) and "point" in obj and obj["point"].strip()


def _truncate_content(content: str) -> str:
    if len(content) > _MAX_CONTENT_LENGTH:
        logger.warning(f"JSON fallback内容过大({len(content)}字符)，截断至{_MAX_CONTENT_LENGTH}字符")
        return content[:_MAX_CONTENT_LENGTH]
    return content


def _parse_cleaned_array(array_content: str) -> list[dict[str, Any]]:
    """方法1a：整体 clean_json_string 后按数组解析。"""
    cleaned_array = clean_json_string(array_content)
    if not cleaned_array:
        return []
    try:
        data = json.loads(cleaned_array)
        if isinstance(data, list):
            return [item for item in data if _is_test_point(item)]
    except Exception:
        logger.debug("整体清理方式提取测试点失败", exc_info=True)
    return []


def _parse_objects_in_array(array_content: str) -> list[dict[str, Any]]:
    """方法1b：把数组拆成单个对象逐个 clean 后解析。"""
    test_points: list[dict[str, Any]] = []
    for obj_str in re.findall(_OBJECT_PATTERN, array_content, re.DOTALL):
        try:
            cleaned = clean_json_string(obj_str)
            if cleaned:
                obj = json.loads(cleaned)
                if _is_test_point(obj):
                    test_points.append(obj)
        except json.JSONDecodeError:
            continue
    return test_points


def _extract_from_array(content: str) -> list[dict[str, Any]]:
    """方法1：截取首个 `[...]`，先整体清理，失败再逐对象清理。"""
    array_match = re.search(r"\[[\s\S]*\]", content)
    if not array_match:
        return []
    array_content = array_match.group(0)

    test_points = _parse_cleaned_array(array_content)
    if test_points:
        logger.info(f"方法1(整体清理)成功提取 {len(test_points)} 个测试点")
        return test_points

    test_points = _parse_objects_in_array(array_content)
    if test_points:
        logger.info(f"方法1(逐个清理)成功提取 {len(test_points)} 个测试点")
    return test_points


def _extract_from_point_matches(content: str) -> list[dict[str, Any]]:
    """方法2：按 `"point": "..."` 反查所在对象片段，逐字段抽取。"""
    test_points: list[dict[str, Any]] = []
    for point_text in re.findall(_POINT_PATTERN, content, re.DOTALL):
        if not (point_text.strip() and len(point_text) > 5):
            continue
        context_start = content.find(point_text)
        if context_start <= 0:
            continue
        obj_start = content.rfind("{", max(0, context_start - 500))
        obj_end = content.find("}", context_start + len(point_text))
        if obj_start < 0 or obj_end <= obj_start:
            continue
        test_point = parse_test_point_object(content[obj_start : obj_end + 1])
        if test_point:
            test_points.append(test_point)
    return test_points


def _apply_continuation(line: str, current_obj: dict[str, Any], buffer: str) -> str:
    """方法3 的续行处理：拼接后尝试取值，成功则写回最后一个键。"""
    buffer += " " + line.strip()
    value = extract_value(buffer)
    if value is None or not current_obj:
        return buffer
    current_obj[next(reversed(current_obj))] = value
    return ""


def _apply_key_line(line: str, current_obj: dict[str, Any], buffer: str) -> str:
    """方法3 的单行处理：`"key": value` 直接落库，值不完整则转为 buffer。"""
    key_match = re.match(r'^\s*"(\w+)"\s*:\s*(.+)$', line)
    if not key_match:
        if buffer and line.startswith('"'):
            return _apply_continuation(line, current_obj, buffer)
        return buffer
    key = key_match.group(1).strip()
    value_part = key_match.group(2).strip()
    value = extract_value(value_part)
    if key and value is not None:
        current_obj[key] = value
        return ""
    if key:
        return value_part
    return buffer


def _extract_from_line_scan(content: str) -> list[dict[str, Any]]:
    """方法3：逐行宽松解析（值可跨行），收集 `{...}` 块内的测试点。"""
    if not re.search(_LOOSE_KEY_PATTERN, content):
        return []

    test_points: list[dict[str, Any]] = []
    current_obj: dict[str, Any] = {}
    in_object = False
    buffer = ""
    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("{"):
            in_object, current_obj, buffer = True, {}, ""
        elif line.startswith("}") and in_object:
            if _is_test_point(current_obj):
                test_points.append(current_obj.copy())
            in_object, current_obj, buffer = False, {}, ""
        elif in_object:
            buffer = _apply_key_line(line, current_obj, buffer)
    return test_points


def extract_json_objects_fallback(content: str) -> list[dict[str, Any]]:
    """四级回退提取测试点：数组整体清理 → 数组逐对象 → point 反查 → 逐行宽松解析。"""
    content = _truncate_content(content)

    test_points = _extract_from_array(content)
    if test_points:
        return test_points

    test_points = _extract_from_point_matches(content)
    test_points.extend(_extract_from_line_scan(content))
    if test_points:
        logger.info(f"Fallback方法共提取 {len(test_points)} 个测试点")
        return test_points
    return []


def parse_test_point_object(text: str) -> dict | None:
    result = {}
    module_match = re.search(r'"module"\s*:\s*"([^"]*)"', text)
    if module_match:
        result["module"] = module_match.group(1)
    func_match = re.search(r'"function"\s*:\s*"([^"]*)"', text)
    if func_match:
        result["function"] = func_match.group(1)
    point_match = re.search(r'"point"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if point_match:
        result["point"] = point_match.group(1)
    priority_match = re.search(r'"priority"\s*:\s*(\d+)', text)
    if priority_match:
        result["priority"] = int(priority_match.group(1))
    if result.get("point") and result["point"].strip():
        return result
    return None


def extract_value(value_part: str) -> Any | None:
    if not value_part or value_part == ",":
        return None
    value_part = value_part.rstrip(",")
    if value_part.startswith('"'):
        end_quote = value_part.rfind('"')
        if end_quote > 0:
            return value_part[1:end_quote]
        return value_part[1:]
    if re.match(r"^-?\d+$", value_part):
        return int(value_part)
    if re.match(r"^-?\d+\.\d+$", value_part):
        return float(value_part)
    if value_part.lower() == "true":
        return True
    if value_part.lower() == "false":
        return False
    return value_part if value_part else None
