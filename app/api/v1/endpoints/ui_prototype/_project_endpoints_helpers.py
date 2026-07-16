"""UI原型项目端点纯辅助函数。

包含流程摘要构建与流程数据序列化等无副作用工具函数，供路由处理函数复用。
"""
from typing import Any

from app.models.project_flow_data import ProjectFlowData


def _count_navigation_edges(navigation_map: dict[str, Any]) -> int:
    edge_count = 0
    for mapping in navigation_map.values():
        if not isinstance(mapping, dict):
            continue
        can_go_to = mapping.get("can_go_to")
        back_to = mapping.get("back_to")
        edge_count += len(can_go_to) if isinstance(can_go_to, list) else 0
        edge_count += len(back_to) if isinstance(back_to, list) else 0
    return edge_count


def _build_flow_summary(merged_flow: Any) -> dict[str, Any]:
    if not isinstance(merged_flow, dict) or not merged_flow:
        return {
            "has_flow": False,
            "node_count": 0,
            "edge_count": 0,
            "entry_screen": "",
            "end_screens": [],
            "branch_count": 0,
            "exception_count": 0,
            "warning_count": 0,
            "key_path_count": 0,
        }

    page_flows = merged_flow.get("page_flows")
    navigation_map = merged_flow.get("navigation_map")
    end_screens = merged_flow.get("end_screens")
    key_user_paths = merged_flow.get("key_user_paths")
    warnings = merged_flow.get("warnings")

    flow_list = page_flows if isinstance(page_flows, list) else []
    nav_map = navigation_map if isinstance(navigation_map, dict) else {}
    end_list = end_screens if isinstance(end_screens, list) else []
    key_paths = key_user_paths if isinstance(key_user_paths, list) else []
    warning_list = warnings if isinstance(warnings, list) else []

    node_names: set[str] = set()
    entry_screen = merged_flow.get("entry_screen")
    if isinstance(entry_screen, str) and entry_screen:
        node_names.add(entry_screen)
    for flow in flow_list:
        if not isinstance(flow, dict):
            continue
        from_screen = flow.get("from_screen")
        to_screen = flow.get("to_screen")
        if isinstance(from_screen, str) and from_screen:
            node_names.add(from_screen)
        if isinstance(to_screen, str) and to_screen:
            node_names.add(to_screen)
    for screen_name, mapping in nav_map.items():
        if isinstance(screen_name, str) and screen_name:
            node_names.add(screen_name)
        if not isinstance(mapping, dict):
            continue
        for key in ("can_go_to", "back_to"):
            values = mapping.get(key)
            if isinstance(values, list):
                node_names.update(v for v in values if isinstance(v, str) and v)
    node_names.update(v for v in end_list if isinstance(v, str) and v)

    branch_count = sum(
        1
        for flow in flow_list
        if isinstance(flow, dict)
        and isinstance(flow.get("condition"), str)
        and flow.get("condition")
    )
    edge_count = len(flow_list) or _count_navigation_edges(nav_map)

    return {
        "has_flow": edge_count > 0 or bool(key_paths),
        "node_count": len(node_names),
        "edge_count": edge_count,
        "entry_screen": entry_screen if isinstance(entry_screen, str) else "",
        "end_screens": [v for v in end_list if isinstance(v, str)],
        "branch_count": branch_count,
        "exception_count": len(warning_list),
        "warning_count": len(warning_list),
        "key_path_count": len(key_paths),
    }


def _serialize_project_flow_data(pfd: ProjectFlowData) -> dict:
    return {
        "id": pfd.id,
        "project_id": pfd.project_id,
        "flow_data": pfd.flow_data,
        "create_time": pfd.create_time.isoformat() if pfd.create_time else None,
        "update_time": pfd.update_time.isoformat() if pfd.update_time else None,
    }
