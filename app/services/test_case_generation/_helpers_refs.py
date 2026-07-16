"""test_case_generation 实体引用构造。

将 ORM 对象（TestPoint / Requirement / UIPrototypeScreen）转换为提示词可用的
引用/描述字典，并递归收集屏幕导航 ID。依赖 _helpers_text 的去重与 JSON 解析工具。
"""
from typing import Any, Dict, List

from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen

from app.services.test_case_generation._helpers_text import (
    _dedupe_ints,
    _extract_function_from_ai_prompt,
)


# ── 实体引用构造 ──
def _test_point_entry(point: TestPoint) -> Dict[str, Any]:
    """构造测试点引用字典，function 从 ai_prompt JSON 提取。"""
    return {
        "id": point.id,
        "module": point.module,
        "function": _extract_function_from_ai_prompt(point.ai_prompt),
        "point": point.point,
        "priority": point.priority,
        "requirement_id": point.requirement_id,
    }


def _test_point_search_text(points: List[TestPoint]) -> str:
    """拼接测试点的 module/point/ai_prompt 文本，供关键词提取。"""
    return " ".join(
        f"{point.module or ''} {point.point or ''} {point.ai_prompt or ''}"
        for point in points
    )


def _requirement_ref(requirement: Requirement) -> Dict[str, Any]:
    """构造需求引用字典。"""
    return {
        "id": requirement.id,
        "req_no": requirement.req_no,
        "title": requirement.title,
        "status": requirement.status,
        "source_file_id": requirement.source_file_id,
    }


def _screen_ref(screen: UIPrototypeScreen, confidence: str) -> Dict[str, Any]:
    """构造 UI 屏幕引用字典。"""
    return {
        "id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "confidence": confidence,
        "parse_status": screen.parse_status,
        "element_count": screen.element_count or 0,
    }


def _screen_desc(screen: UIPrototypeScreen, confidence: str = "matched") -> Dict[str, Any]:
    """构造 UI 屏幕描述字典（含元素统计）。"""
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
    """递归收集屏幕的 related_screens/navigation_flow 中的屏幕 ID。"""
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
