import json
import re
from typing import Dict, Any, Optional, List
from loguru import logger

from app.utils.ai_client_parser._json_fixer import clean_json_string


def extract_json_objects_fallback(content: str) -> List[Dict[str, Any]]:
    MAX_CONTENT_LENGTH = 50000
    if len(content) > MAX_CONTENT_LENGTH:
        logger.warning(f"JSON fallback内容过大({len(content)}字符)，截断至{MAX_CONTENT_LENGTH}字符")
        content = content[:MAX_CONTENT_LENGTH]
    test_points = []
    array_match = re.search(r'\[[\s\S]*\]', content)
    if array_match:
        array_content = array_match.group(0)
        cleaned_array = clean_json_string(array_content)
        if cleaned_array:
            try:
                data = json.loads(cleaned_array)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'point' in item and item['point'].strip():
                            test_points.append(item)
                    if test_points:
                        logger.info(f"方法1(整体清理)成功提取 {len(test_points)} 个测试点")
                        return test_points
            except Exception:
                logger.debug("整体清理方式提取测试点失败", exc_info=True)
        object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        objects = re.findall(object_pattern, array_content, re.DOTALL)
        for obj_str in objects:
            try:
                cleaned = clean_json_string(obj_str)
                if cleaned:
                    obj = json.loads(cleaned)
                    if isinstance(obj, dict) and 'point' in obj and obj['point'].strip():
                        test_points.append(obj)
            except json.JSONDecodeError:
                continue
        if test_points:
            logger.info(f"方法1(逐个清理)成功提取 {len(test_points)} 个测试点")
            return test_points
    point_pattern = r'"point"\s*:\s*"([^"]*(?:[^"]|"{2}){0,5}?)"'
    matches = re.findall(point_pattern, content, re.DOTALL)
    if matches:
        for point_text in matches:
            if point_text.strip() and len(point_text) > 5:
                context_start = content.find(point_text)
                if context_start > 0:
                    obj_start = content.rfind('{', max(0, context_start - 500))
                    obj_end = content.find('}', context_start + len(point_text))
                    if obj_start >= 0 and obj_end > obj_start:
                        obj_str = content[obj_start:obj_end + 1]
                        test_point = parse_test_point_object(obj_str)
                        if test_point:
                            test_points.append(test_point)
    object_pattern_loose = r'"(?:module|function|point|priority)"\s*:\s*'
    if re.search(object_pattern_loose, content):
        lines = content.split('\n')
        current_obj = {}
        in_object = False
        buffer = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('{'):
                in_object = True
                current_obj = {}
                buffer = ""
                continue
            if line.startswith('}') and in_object:
                if current_obj.get('point') and current_obj['point'].strip():
                    test_points.append(current_obj.copy())
                in_object = False
                current_obj = {}
                buffer = ""
                continue
            if in_object:
                key_match = re.match(r'^\s*"(\w+)"\s*:\s*(.+)$', line)
                if key_match:
                    key = key_match.group(1).strip()
                    value_part = key_match.group(2).strip()
                    value = extract_value(value_part)
                    if key and value is not None:
                        current_obj[key] = value
                        buffer = ""
                    elif key:
                        buffer = value_part
                elif buffer and line.startswith('"'):
                    buffer += " " + line.strip()
                    value = extract_value(buffer)
                    if value is not None:
                        last_key = list(current_obj.keys())[-1] if current_obj else None
                        if last_key:
                            current_obj[last_key] = value
                            buffer = ""
    if test_points:
        logger.info(f"Fallback方法共提取 {len(test_points)} 个测试点")
        return test_points
    return []


def parse_test_point_object(text: str) -> Optional[Dict]:
    result = {}
    module_match = re.search(r'"module"\s*:\s*"([^"]*)"', text)
    if module_match:
        result['module'] = module_match.group(1)
    func_match = re.search(r'"function"\s*:\s*"([^"]*)"', text)
    if func_match:
        result['function'] = func_match.group(1)
    point_match = re.search(r'"point"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if point_match:
        result['point'] = point_match.group(1)
    priority_match = re.search(r'"priority"\s*:\s*(\d+)', text)
    if priority_match:
        result['priority'] = int(priority_match.group(1))
    if result.get('point') and result['point'].strip():
        return result
    return None


def extract_value(value_part: str) -> Optional[Any]:
    if not value_part or value_part == ',':
        return None
    value_part = value_part.rstrip(',')
    if value_part.startswith('"'):
        end_quote = value_part.rfind('"')
        if end_quote > 0:
            return value_part[1:end_quote]
        return value_part[1:]
    if re.match(r'^-?\d+$', value_part):
        return int(value_part)
    if re.match(r'^-?\d+\.\d+$', value_part):
        return float(value_part)
    if value_part.lower() == 'true':
        return True
    if value_part.lower() == 'false':
        return False
    return value_part if value_part else None
