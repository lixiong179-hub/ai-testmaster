"""test_case_generation 实体引用构造子模块。

从 _base_helpers.py 拆分而来，包含测试点/需求/屏幕的引用字典构造
与导航屏幕ID收集。所有函数均为模块级纯函数。

业务原因：_base_helpers.py 单文件超过 350 行限制，按职责将实体引用
构造函数集中到独立文件，主模块聚焦于文本处理与上下文预算控制。
"""
from typing import Any, Dict, List

from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen
from app.services.test_case_generation.test_point_loader import (
    _extract_function_from_ai_prompt,
)

DEFAULT_MATCHED_REQUIREMENT_LIMIT = 3
DEFAULT_MATCHED_UI_SCREEN_LIMIT = 3
DEFAULT_ADJACENT_UI_SCREEN_LIMIT = 2


def _test_point_entry(point: TestPoint) -> Dict[str, Any]:
    return {
        "id": point.id,
        "module": point.module,
        "function": _extract_function_from_ai_prompt(point.ai_prompt),
        "point": point.point,
        "priority": point.priority,
        "requirement_id": point.requirement_id,
    }


def _test_point_search_text(points: List[TestPoint]) -> str:
    return " ".join(
        f"{point.module or ''} {point.point or ''} {point.ai_prompt or ''}"
        for point in points
    )


def _requirement_ref(requirement: Requirement) -> Dict[str, Any]:
    return {
        "id": requirement.id,
        "req_no": requirement.req_no,
        "title": requirement.title,
        "status": requirement.status,
        "source_file_id": requirement.source_file_id,
    }


def _screen_ref(screen: UIPrototypeScreen, confidence: str) -> Dict[str, Any]:
    return {
        "id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "confidence": confidence,
        "parse_status": screen.parse_status,
        "element_count": screen.element_count or 0,
    }


def _screen_desc(screen: UIPrototypeScreen, confidence: str = "matched") -> Dict[str, Any]:
    return {
        "screen_id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "parse_status": screen.parse_status,
        "summary": screen.summary or "",
        "element_count": screen.element_count or 0,
        "button_count": screen.button_count or 0,
        "input_count": screen.input_count or 0,
        "description": screen.summary or "",
        "match_confidence": confidence,
    }


def _collect_navigation_screen_ids(screen: UIPrototypeScreen) -> List[int]:
    ids: List[int] = []

    def collect(value: Any) -> None:
        if isinstance(value, int):
            ids.append(value)
        elif isinstance(value, str):
            if value.isdigit():
                ids.append(int(value))
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"id", "screen_id", "target", "target_id", "to", "next"}:
                    collect(item)
                elif isinstance(item, (dict, list)):
                    collect(item)

    collect(screen.related_screens)
    collect(screen.navigation_flow)
    return _dedupe_ints(ids)


def _dedupe_ints(values: List[int]) -> List[int]:
    if not values:
        return []
    result: List[int] = []
    seen = set()
    for value in values:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


__all__ = [
    "DEFAULT_MATCHED_REQUIREMENT_LIMIT",
    "DEFAULT_MATCHED_UI_SCREEN_LIMIT",
    "DEFAULT_ADJACENT_UI_SCREEN_LIMIT",
    "_collect_navigation_screen_ids",
    "_dedupe_ints",
    "_requirement_ref",
    "_screen_desc",
    "_screen_ref",
    "_test_point_entry",
    "_test_point_search_text",
]
