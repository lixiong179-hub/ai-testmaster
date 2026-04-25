"""UI Spec 格式化函数 - 唯一实现，消除 ai_prompt_builder 和 ai_prompt_mixin 的重复逻辑。

提供两个公共函数:
    - format_ui_spec_for_prompt: 单个 UI 规格格式化
    - format_ui_specs_list: UI 规格列表批量格式化
"""
from typing import List, Dict, Any


def format_ui_spec_for_prompt(screen_name: str, ui_spec: Dict[str, Any]) -> str:
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

    if ui_spec.get('purpose'):
        parts.append(f"页面功能：{ui_spec['purpose']}")

    regions = ui_spec.get('regions', {})
    if regions:
        parts.append("页面区域：")
        if isinstance(regions, dict):
            for region_name, region_desc in regions.items():
                if region_desc:
                    parts.append(f"  - {region_name}: {region_desc}")
        elif isinstance(regions, list):
            for region in regions:
                if isinstance(region, dict):
                    name = region.get('name', '')
                    desc = region.get('desc', region.get('description', ''))
                    if name or desc:
                        parts.append(f"  - {name}: {desc}")

    elements = ui_spec.get('elements', [])
    if elements:
        parts.append(f"页面元素（共{len(elements)}个）：")
        for elem in elements[:30]:
            elem_type = elem.get('type', '未知')
            label = elem.get('label', '') or elem.get('semantic', '') or elem.get('name', '')
            state = elem.get('state', 'normal')
            interactive = elem.get('interactive', False)
            desc = elem.get('description', '')
            parts.append(f"  - [{elem_type}] {label} | 状态:{state} | 可交互:{interactive} | {desc}")

    navigation = ui_spec.get('navigation', {})
    if navigation:
        parts.append("导航结构：")
        for nav_key, nav_val in navigation.items():
            if nav_val:
                parts.append(f"  - {nav_key}: {nav_val}")

    layout_checks = ui_spec.get('layout_constraints', [])
    if layout_checks:
        parts.append(f"布局约束（共{len(layout_checks)}项）：")
        for check in layout_checks[:10]:
            desc = check.get('description', '')
            if desc:
                parts.append(f"  - {desc}")

    flows = ui_spec.get('flows', {})
    if flows:
        next_screens = flows.get('expected_next_screens', [])
        if next_screens:
            parts.append(f"预期跳转页面：{', '.join(next_screens)}")

    return "\n".join(parts)


def format_ui_specs_list(ui_specs: List[Dict[str, Any]]) -> str:
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
