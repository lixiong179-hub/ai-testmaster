from typing import Any

from app.services.prompt_builder.helpers import (
    _safe_int,
    _infer_condition,
    _render_flow_meta_hint,
    _render_edge_hint,
)
from app.services.prompt_builder.case_prompt._node_format import (
    _format_node_elements,
    _build_image_ref,
)

_CHILD_LABELS = {"branch": "分支", "exception": "异常"}
_CHILD_CATEGORIES = {"branch": "boundary", "exception": "exception"}
_CHILD_TYPES = ("branch", "exception")

_BYPASS_SINGLE_HINT = " [注意: 此步骤可能出现{name}，需关闭弹窗后验证主流程页面元素仍可正常交互]"
_BYPASS_MULTI_HINT = " [注意: 此步骤可能依次出现以下弹窗，需逐个关闭后验证主流程页面元素仍可正常交互: {items}]"
_BYPASS_SECTION_NOTE = (
    "旁路说明: 旁路是主流程执行中自动弹出的干扰性弹窗或浮层，"
    "不需要为每个旁路单独生成用例，而是在主干正向用例的对应步骤中"
    '增加"关闭弹窗"操作即可。'
)


def _bypass_target_name(edge: dict[str, Any], node_map: dict[Any, dict[str, Any]]) -> str:
    target_id = _safe_int(edge.get("target"))
    target_node = node_map.get(target_id, {}) if target_id is not None else {}
    return target_node.get("screen_name", "弹窗")


def _render_bypass_hint(
    bypass_edges: list[dict[str, Any]],
    node_map: dict[Any, dict[str, Any]],
) -> str:
    """主干步骤上的旁路弹窗提示；无旁路时返回空串。"""
    if not bypass_edges:
        return ""
    if len(bypass_edges) == 1:
        return _BYPASS_SINGLE_HINT.format(name=_bypass_target_name(bypass_edges[0], node_map))
    items = [f"{idx}. {_bypass_target_name(edge, node_map)}" for idx, edge in enumerate(bypass_edges, 1)]
    return _BYPASS_MULTI_HINT.format(items="; ".join(items))


def _render_main_step(
    index: int,
    node: dict[str, Any],
    node_map: dict[Any, dict[str, Any]],
    bypass_by_source: dict[int, list[dict[str, Any]]],
    include_images: bool,
) -> str:
    """渲染主干流程中的单个步骤行。"""
    elements = node.get("ui_spec_elements", []) or []
    summary = (node.get("summary") or "").strip()
    summary_suffix = f" 摘要:{summary}" if summary else ""
    bypass_hint = _render_bypass_hint(bypass_by_source.get(node.get("screen_id"), []), node_map)
    return (
        f"步骤 {index}: [截图{index} - {node.get('screen_name', '')}]"
        f" 元素: {_format_node_elements(elements)}{_build_image_ref(node, include_images)}"
        f"{summary_suffix}{bypass_hint}"
    )


def _render_source_elements_hint(source_node: dict[str, Any]) -> str:
    """从源节点元素描述中取前 3 个元素名，作为前置条件提示。"""
    source_el_desc = _format_node_elements(source_node.get("ui_spec_elements", []) or [])
    if not source_el_desc:
        return "页面已加载完成"
    key_elements = [el_part.split(":")[1].split("[")[0] for el_part in source_el_desc.split(";")[:3] if ":" in el_part]
    return "、".join(key_elements) if key_elements else "页面已加载完成"


def _render_child_scene(
    scene_idx: int,
    step_idx: int,
    source_node: dict[str, Any],
    edge: dict[str, Any],
    ctype: str,
    node_map: dict[Any, dict[str, Any]],
    include_images: bool,
) -> list[str] | None:
    """渲染一条分支/异常子场景；目标无效时返回 None。"""
    target_id = _safe_int(edge.get("target"))
    if target_id is None:
        return None

    target_node = node_map.get(target_id, {})
    label = _CHILD_LABELS[ctype]
    category = _CHILD_CATEGORIES[ctype]
    source_name = source_node.get("screen_name", "")
    target_summary = (target_node.get("summary") or "").strip()
    target_summary_suffix = f" 摘要:{target_summary}" if target_summary else ""
    condition = _infer_condition(edge, ctype, target_node, source_node)
    hints = _render_flow_meta_hint(target_node.get("flow_meta") or {}, ctype) + _render_edge_hint(edge)
    elements_hint = _render_source_elements_hint(source_node)

    return [
        f"### 场景{scene_idx}: {label}流程（源于步骤{step_idx}[{source_name}]，case_category={category}）",
        f"触发条件: {condition}{hints}",
        f"起始点: 从步骤{step_idx}[{source_name}]触发{label}，进入 [{target_node.get('screen_name', '')}]",
        f"目标页面: [截图 - {target_node.get('screen_name', '')}]"
        f" 元素: {_format_node_elements(target_node.get('ui_spec_elements', []) or [])}"
        f"{_build_image_ref(target_node, include_images)}{target_summary_suffix}",
        f"用例要求: 仅验证此{label}场景，"
        f"此用例依赖场景1（主干正向用例）执行到步骤{step_idx}后的页面状态，"
        f"depends_on 必须填写场景1的用例标题，anchor_step 必须填写{step_idx}；"
        f"前置条件只需写数据准备（如Mock接口返回值）和页面状态"
        f'（如"已处于{source_name}，可见{elements_hint}等元素"），'
        f"不需要重复描述到达路径（执行引擎会自动执行场景1到步骤{step_idx}后继续）；"
        f"步骤从触发{label}开始，预期结果聚焦{label}本身的表现",
        "",
    ]


def _collect_bypass_edges(
    main_nodes: list[dict[str, Any]],
    bypass_by_source: dict[int, list[dict[str, Any]]],
) -> list[tuple[int, dict[str, Any], dict[str, Any], int]]:
    """汇总所有有效旁路连线，附带所属主干步骤序号。"""
    items = []
    for step_idx, node in enumerate(main_nodes, 1):
        for edge in bypass_by_source.get(node.get("screen_id"), []):
            target_id = _safe_int(edge.get("target"))
            if target_id is not None:
                items.append((step_idx, node, edge, target_id))
    return items


def _append_bypass_section(
    parts: list[str],
    scene_idx: int,
    items: list[tuple[int, dict[str, Any], dict[str, Any], int]],
    node_map: dict[Any, dict[str, Any]],
) -> None:
    """渲染末尾的旁路流程章节。"""
    parts.append(f"### 场景{scene_idx}: 旁路流程（弹窗/浮层拦截，case_category=boundary）")
    parts.append(_BYPASS_SECTION_NOTE)
    for step_idx, node, edge, target_id in items:
        target_node = node_map.get(target_id, {})
        condition = _infer_condition(edge, "bypass", target_node, node)
        hints = _render_flow_meta_hint(target_node.get("flow_meta") or {}, "bypass") + _render_edge_hint(edge)
        parts.append(
            f"- 步骤{step_idx}[{node.get('screen_name', '')}]: "
            f"{condition}{hints} → "
            f"关闭[{target_node.get('screen_name', '弹窗')}]后继续主流程"
        )
    parts.append("")


def _append_nested_flow(
    parts: list[str],
    main_nodes: list[dict[str, Any]],
    node_map: dict[Any, dict[str, Any]],
    branch_by_source: dict[int, list[dict[str, Any]]],
    exception_by_source: dict[int, list[dict[str, Any]]],
    bypass_by_source: dict[int, list[dict[str, Any]]],
    include_images: bool,
) -> None:
    parts.append("## UI原型图流程结构\n")
    parts.append("以下流程按场景独立呈现，每个场景必须生成独立的测试用例，禁止将不同场景的步骤混合在同一条用例中。\n")

    parts.append("### 场景1: 主干正向流程（完整覆盖，步骤不可颠倒、不可遗漏）")
    for index, node in enumerate(main_nodes, 1):
        parts.append(_render_main_step(index, node, node_map, bypass_by_source, include_images))
    parts.append("")

    child_sources = {"branch": branch_by_source, "exception": exception_by_source}
    scene_idx = 2
    for step_idx, node in enumerate(main_nodes, 1):
        for ctype in _CHILD_TYPES:
            for edge in child_sources[ctype].get(node.get("screen_id"), []):
                scene_lines = _render_child_scene(scene_idx, step_idx, node, edge, ctype, node_map, include_images)
                if scene_lines is None:
                    continue
                parts.extend(scene_lines)
                scene_idx += 1

    bypass_items = _collect_bypass_edges(main_nodes, bypass_by_source)
    if bypass_items:
        _append_bypass_section(parts, scene_idx, bypass_items, node_map)

    parts.append("")
