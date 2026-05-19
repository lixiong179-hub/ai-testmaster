import json
import re
from typing import Optional


def _repair_truncated_json(json_str: str) -> Optional[str]:
    if not json_str or len(json_str) < 10:
        return None
    repaired = json_str.rstrip()
    if repaired.endswith(']') or repaired.endswith('}'):
        return None
    in_string = False
    escape_next = False
    for ch in repaired:
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
        repaired += '"'
    last_brace = repaired.rfind('}')
    last_bracket = repaired.rfind(']')
    last_struct = max(last_brace, last_bracket)
    if last_struct > 0:
        repaired = repaired[:last_struct + 1]
    repaired = re.sub(r',\s*$', '', repaired)
    open_brackets = 0
    open_braces = 0
    in_string = False
    escape_next = False
    for ch in repaired:
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
        if ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1
        elif ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
    while open_braces > 0:
        repaired += '}'
        open_braces -= 1
    while open_brackets > 0:
        repaired += ']'
        open_brackets -= 1
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return None
