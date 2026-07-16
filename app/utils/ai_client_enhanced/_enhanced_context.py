import json
from typing import Dict, Any, List


AI_GENERATE_MAX_TOKENS = 8192
AI_GENERATE_MAX_TOKENS_FULL = 16384


def _as_dict_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_test_points(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    points_by_id: Dict[str, Dict[str, Any]] = {}
    anonymous_points: List[Dict[str, Any]] = []

    for key in ("test_points", "test_points_data", "test_point", "current_test_point"):
        for point in _as_dict_list(context.get(key)):
            point_id = point.get("id")
            if point_id is None:
                anonymous_points.append(point)
                continue
            point_key = str(point_id)
            merged = dict(points_by_id.get(point_key, {}))
            for field, value in point.items():
                if value not in (None, "", []):
                    merged[field] = value
            points_by_id[point_key] = merged

    return list(points_by_id.values()) + anonymous_points


def _normalize_ui_specs(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _stringify_ui_description(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("screen_name") or item.get("file_name") or item.get("name") or "未命名"
                desc = item.get("description") or item.get("summary") or json.dumps(item, ensure_ascii=False)
                parts.append(f"【{name}】\n{desc}")
            elif item:
                parts.append(str(item))
        return "\n\n".join(parts)
    return ""


def _resolve_max_tokens(context: Dict[str, Any], *, graph_mode: bool) -> int:
    test_points = _normalize_test_points(context)
    if graph_mode or len(test_points) > 1 or context.get("history_cases"):
        return AI_GENERATE_MAX_TOKENS_FULL
    return AI_GENERATE_MAX_TOKENS
