"""UI Spec 格式化函数 - 唯一实现，消除 ai_prompt_builder 和 ai_prompt_mixin 的重复逻辑。

提供两个公共函数:
    - format_ui_spec_for_prompt: 单个 UI 规格格式化
    - format_ui_specs_list: UI 规格列表批量格式化
"""

from typing import Any


def _format_purpose(ui_spec: dict[str, Any]) -> list[str]:
    """页面功能描述。"""
    if not ui_spec.get("purpose"):
        return []
    return [f"页面功能：{ui_spec['purpose']}"]


def _format_regions(regions) -> list[str]:
    """页面区域划分：dict（名称→描述）或 list（含 name/desc）。"""
    if not regions:
        return []
    lines = ["页面区域："]
    if isinstance(regions, dict):
        for region_name, region_desc in regions.items():
            if region_desc:
                lines.append(f"  - {region_name}: {region_desc}")
    elif isinstance(regions, list):
        for region in regions:
            if isinstance(region, dict):
                name = region.get("name", "")
                desc = region.get("desc", region.get("description", ""))
                if name or desc:
                    lines.append(f"  - {name}: {desc}")
    return lines


def _format_elements(elements: list) -> list[str]:
    """页面元素列表（最多 30 个）。"""
    if not elements:
        return []
    lines = [f"页面元素（共{len(elements)}个）："]
    for elem in elements[:30]:
        elem_type = elem.get("type", "未知")
        label = elem.get("label", "") or elem.get("semantic", "") or elem.get("name", "")
        state = elem.get("state", "normal")
        interactive = elem.get("interactive", False)
        desc = elem.get("description", "")
        lines.append(f"  - [{elem_type}] {label} | 状态:{state} | 可交互:{interactive} | {desc}")
    return lines


def _format_navigation(navigation) -> list[str]:
    """导航结构。"""
    if not navigation:
        return []
    lines = ["导航结构："]
    for nav_key, nav_val in navigation.items():
        if nav_val:
            lines.append(f"  - {nav_key}: {nav_val}")
    return lines


def _format_layout_constraints(layout_checks: list) -> list[str]:
    """布局约束（最多 10 条）。"""
    if not layout_checks:
        return []
    lines = [f"布局约束（共{len(layout_checks)}项）："]
    for check in layout_checks[:10]:
        desc = check.get("description", "")
        if desc:
            lines.append(f"  - {desc}")
    return lines


def _format_flows(flows) -> list[str]:
    """页面跳转关系。"""
    if not flows:
        return []
    next_screens = flows.get("expected_next_screens", [])
    if not next_screens:
        return []
    return [f"预期跳转页面：{', '.join(next_screens)}"]


def format_ui_spec_for_prompt(screen_name: str, ui_spec: dict[str, Any]) -> str:
    """将 UI 规格数据格式化为 Prompt 友好的文本描述（唯一实现）。

    格式化内容包括:
        - 页面功能描述
        - 页面区域划分
        - 页面元素列表（类型、标签、状态、交互性）
        - 导航结构
        - 布局约束
        - 页面跳转关系

    Args:
        screen_name: 页面名称。
        ui_spec: UI 规格字典，包含 purpose/regions/elements/navigation 等。

    Returns:
        格式化后的文本描述。
    """
    parts = [f"【页面：{screen_name}】"]
    parts.extend(_format_purpose(ui_spec))
    parts.extend(_format_regions(ui_spec.get("regions", {})))
    parts.extend(_format_elements(ui_spec.get("elements", [])))
    parts.extend(_format_navigation(ui_spec.get("navigation", {})))
    parts.extend(_format_layout_constraints(ui_spec.get("layout_constraints", [])))
    parts.extend(_format_flows(ui_spec.get("flows", {})))
    return "\n".join(parts)


def format_ui_specs_list(ui_specs: list[dict[str, Any]]) -> str:
    """将 UI 规格列表格式化为 Prompt 文本。

    Args:
        ui_specs: UI 规格列表，每项包含 screen_name 和 ui_spec。

    Returns:
        格式化后的文本，多项以双换行分隔；空列表返回空字符串。
    """
    if not ui_specs:
        return ""
    spec_parts = []
    for spec_item in ui_specs:
        screen_name = spec_item.get("screen_name", "未命名页面")
        spec = spec_item.get("ui_spec", {})
        if spec:
            spec_parts.append(format_ui_spec_for_prompt(screen_name, spec))
    return "\n\n".join(spec_parts) if spec_parts else ""
