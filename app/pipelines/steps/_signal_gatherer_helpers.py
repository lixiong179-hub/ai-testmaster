"""SignalGatherer 辅助函数模块。

从 signal_gatherer.py 拆分，包含信号采集所需的所有辅助函数：
文件内容加载、UI原型解析、测试点加载、xmind解析、置信度计算等。

公共符号通过 signal_gatherer.py 重新导出，保持 import 路径不变。
"""

import json
from typing import Any


from app.pipelines.context import PipelineContext


def _load_file_content(ctx: PipelineContext, file_id: int | None, project_id: int) -> str:
    if not file_id:
        return ""
    from app.crud import file as file_crud

    file_record = file_crud.get_file_by_id(ctx.db, file_id, project_id)
    if not file_record:
        return ""
    return file_record.content or ""


def _load_change_notes_from_input(inp: Any) -> str:
    payload = inp.payload if getattr(inp, "payload", None) and isinstance(inp.payload, dict) else {}
    for key in ("notes", "change_notes", "description", "summary", "content"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _load_ui_from_input(ctx: PipelineContext, inp: Any, project_id: int) -> tuple[list[dict], list[dict], list[int]]:
    """按 payload 指定 → mockup 文件 → 全量兜底 三级顺序取 UI 原型页面（G-8 B5f 拆分）。

    与原实现一致：命中前一级即不再往下取；`file_ids` 仅在 mockup 文件命中时记录。
    """
    payload = inp.payload if getattr(inp, "payload", None) and isinstance(inp.payload, dict) else {}
    screens = _payload_ui_screens(ctx, payload, project_id)
    file_ids: list[int] = []
    if not screens:
        screens, file_ids = _file_ui_screens(ctx, getattr(inp, "file_id", None), project_id)
    if not screens:
        screens = _all_spec_ui_screens(ctx, project_id)
    ui_descriptions, ui_specs = _split_ui_screens(screens)
    return ui_descriptions, ui_specs, file_ids


def _payload_ui_screens(ctx: PipelineContext, payload: dict[str, Any], project_id: int) -> list[Any]:
    """payload 显式指定的页面：优先 screen_ids，其次 prototype_project_ids。"""
    if not payload:
        return []
    screen_ids = _collect_ui_screen_ids(payload)
    if screen_ids:
        from app.models.ui_prototype import UIPrototypeScreen

        return _query_ui_screens(
            ctx,
            UIPrototypeScreen.project_id == project_id,
            UIPrototypeScreen.id.in_(screen_ids),
        )
    prototype_project_ids = _collect_prototype_project_ids(payload)
    if not prototype_project_ids:
        return []
    from app.models.ui_prototype import UIPrototypeScreen

    return _query_ui_screens(
        ctx,
        UIPrototypeScreen.project_id == project_id,
        UIPrototypeScreen.prototype_project_id.in_(prototype_project_ids),
        UIPrototypeScreen.parse_status == "completed",
    )


def _file_ui_screens(ctx: PipelineContext, file_id: int | None, project_id: int) -> tuple[list[Any], list[int]]:
    """按 mockup 文件名匹配原型页面；非 mockup 资源返回空。"""
    if not file_id:
        return [], []
    from app.crud import file as file_crud
    from app.models.ui_prototype import UIPrototypeScreen

    file_record = file_crud.get_file_by_id(ctx.db, file_id, project_id)
    if not file_record or file_record.resource_type != "ui_mockup":
        return [], []
    screens = _query_ui_screens(
        ctx,
        UIPrototypeScreen.project_id == project_id,
        UIPrototypeScreen.prototype_name == file_record.file_name,
        UIPrototypeScreen.parse_status == "completed",
        with_id_order=False,
    )
    return screens, [file_id]


def _all_spec_ui_screens(ctx: PipelineContext, project_id: int) -> list[Any]:
    """兜底：本项目全部已解析且有 ui_spec 的页面。"""
    from app.models.ui_prototype import UIPrototypeScreen

    return _query_ui_screens(
        ctx,
        UIPrototypeScreen.project_id == project_id,
        UIPrototypeScreen.parse_status == "completed",
        UIPrototypeScreen.ui_spec.isnot(None),
        with_id_order=False,
    )


def _query_ui_screens(ctx: PipelineContext, *conditions: Any, with_id_order: bool = True) -> list[Any]:
    from app.models.ui_prototype import UIPrototypeScreen

    query = ctx.db.query(UIPrototypeScreen).filter(*conditions)
    if with_id_order:
        return query.order_by(UIPrototypeScreen.screen_order, UIPrototypeScreen.id).all()
    return query.order_by(UIPrototypeScreen.screen_order).all()


def _split_ui_screens(screens: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """页面 → (描述列表, ui_spec 列表)，按 screen_id 去重（保留首次出现）。"""
    ui_descriptions: list[dict[str, Any]] = []
    ui_specs: list[dict[str, Any]] = []
    seen_screen_ids: set = set()
    for screen in screens:
        if screen.id in seen_screen_ids:
            continue
        seen_screen_ids.add(screen.id)
        ui_descriptions.append(
            {
                "screen_id": screen.id,
                "screen_name": screen.screen_name,
                "description": screen.summary or "",
            }
        )
        if screen.ui_spec:
            ui_specs.append(
                {
                    "screen_id": screen.id,
                    "screen_name": screen.screen_name,
                    "ui_spec": screen.ui_spec,
                }
            )
    return ui_descriptions, ui_specs


def _collect_ui_screen_ids(payload: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for key in ("screen_ids", "screen_id", "ui_prototype_id"):
        values.extend(_coerce_id_list(payload.get(key)))
    return sorted(set(values))


def _collect_prototype_project_ids(payload: dict[str, Any]) -> list[int]:
    values: list[int] = []
    for key in ("prototype_project_id", "ui_project_id"):
        values.extend(_coerce_id_list(payload.get(key)))
    return sorted(set(values))


def _coerce_id_list(value: Any) -> list[int]:
    if value is None:
        return []
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    ids = []
    for item in raw_values:
        try:
            num = int(item)
        except (TypeError, ValueError):
            continue
        if num > 0:
            ids.append(num)
    return ids


def _load_test_points_from_input(ctx: PipelineContext, inp: Any, project_id: int) -> list[dict[str, Any]]:
    from app.models.test_point import TestPoint

    if inp.payload and isinstance(inp.payload, dict):
        point_ids = inp.payload.get("test_point_ids", [])
        if point_ids:
            points = (
                ctx.db.query(TestPoint)
                .filter(
                    TestPoint.id.in_(point_ids),
                    TestPoint.project_id == project_id,
                )
                .all()
            )
            return [_format_test_point(p) for p in points]

    points = (
        ctx.db.query(TestPoint)
        .filter(
            TestPoint.project_id == project_id,
        )
        .order_by(TestPoint.priority.asc(), TestPoint.id.asc())
        .all()
    )
    return [_format_test_point(p) for p in points]


def _check_is_old_project(ctx: PipelineContext, project_id: int) -> bool:
    from app.models.test_case import TestCase as TC

    count = (
        ctx.db.query(TC)
        .filter(
            TC.project_id == project_id,
            TC.lifecycle_status != "archived",
            TC.is_deleted.is_(False),
        )
        .count()
    )
    return count > 0


def _parse_xmind_to_testpoints(payload: dict[str, Any], project_id: int) -> list[dict[str, Any]]:
    xmind_content = payload.get("xmind_content", "")
    if not xmind_content:
        return []
    try:
        data = json.loads(xmind_content) if isinstance(xmind_content, str) else xmind_content
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        data = [data]

    results = []
    for idx, item in enumerate(data):
        if isinstance(item, dict):
            results.append(
                {
                    "id": -(idx + 1),
                    "module": item.get("module", "xmind"),
                    "function": item.get("function", ""),
                    "point": item.get("point", item.get("title", f"xmind节点{idx + 1}")),
                    "priority": item.get("priority", 3),
                }
            )
    return results


def _format_test_point(point: Any) -> dict[str, Any]:
    function = ""
    if point.ai_prompt:
        try:
            data = json.loads(point.ai_prompt)
            if isinstance(data, dict):
                function = str(data.get("function", "") or "")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return {
        "id": point.id,
        "module": point.module,
        "function": function,
        "point": point.point,
        "priority": point.priority,
    }


def _compute_signal_confidence(payload: dict[str, Any]) -> float:
    score = 0.0
    if payload.get("has_prd"):
        score += 0.4
    if payload.get("has_ui"):
        score += 0.3
    if payload.get("has_testpoints"):
        score += 0.3
    if payload.get("has_change_notes"):
        score += 0.1
    return min(score, 1.0)


__all__ = [
    "_load_file_content",
    "_load_change_notes_from_input",
    "_load_ui_from_input",
    "_collect_ui_screen_ids",
    "_collect_prototype_project_ids",
    "_coerce_id_list",
    "_load_test_points_from_input",
    "_check_is_old_project",
    "_parse_xmind_to_testpoints",
    "_format_test_point",
    "_compute_signal_confidence",
]
