import json
import re


#: 结构字符 → (方括号增量, 花括号增量)。
_STRUCT_DELTAS = {"[": (1, 0), "]": (-1, 0), "{": (0, 1), "}": (0, -1)}


def _scan_json_state(text: str) -> tuple[bool, int, int]:
    """扫描 JSON 文本，返回 (结尾是否处于字符串内, 未闭合 `[` 数, 未闭合 `{` 数)。

    字符串内的结构字符与转义字符不计入括号配对。负数（多余闭括号）原样返回，
    由调用方决定是否钳制——`_repair_truncated_json` 只用正数做补齐。
    """
    in_string = False
    escape_next = False
    open_brackets = 0
    open_braces = 0
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        delta = _STRUCT_DELTAS.get(ch)
        if delta:
            open_brackets += delta[0]
            open_braces += delta[1]
    return in_string, open_brackets, open_braces


def _repair_truncated_json(json_str: str) -> str | None:
    if not json_str or len(json_str) < 10:
        return None
    repaired = json_str.rstrip()
    if repaired.endswith("]") or repaired.endswith("}"):
        return None

    # ① 截断点落在字符串内 → 先补引号，否则后续括号补齐全部作废
    in_string, _, _ = _scan_json_state(repaired)
    if in_string:
        repaired += '"'

    # ② 砍掉最后一个结构字符之后的残渣（如 `..., "titl`），再清掉悬空逗号
    last_struct = max(repaired.rfind("}"), repaired.rfind("]"))
    if last_struct > 0:
        repaired = repaired[: last_struct + 1]
    repaired = re.sub(r",\s*$", "", repaired)

    # ③ 按未闭合数量补齐（负数视为多余闭括号，不处理）
    _, open_brackets, open_braces = _scan_json_state(repaired)
    repaired += "}" * max(open_braces, 0)
    repaired += "]" * max(open_brackets, 0)

    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return None
