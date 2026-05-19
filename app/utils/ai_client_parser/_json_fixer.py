import json
import re
from typing import Optional
from loguru import logger


def fix_common_json_issues(json_str: str) -> Optional[str]:
    if not json_str:
        return None
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        pass
    json_str = re.sub(r'//[^\n]*', '', json_str)
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
