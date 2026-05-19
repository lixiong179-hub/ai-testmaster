from typing import List, Dict, Any

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


def _append_nested_flow(
    parts: List[str],
    main_nodes: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    branch_by_source: Dict[int, List[Dict[str, Any]]],
    exception_by_source: Dict[int, List[Dict[str, Any]]],
    bypass_by_source: Dict[int, List[Dict[str, Any]]],
    include_images: bool
) -> None:
    parts.append("## UI原型图流程结构\n")
    parts.append(
        "以下流程按场景独立呈现，每个场景必须生成独立的测试用例，"
        "禁止将不同场景的步骤混合在同一条用例中。\n"
    )

    parts.append("### 场景1: 主干正向流程（完整覆盖，步骤不可颠倒、不可遗漏）")
    for i, node in enumerate(main_nodes, 1):
        screen_id = node.get('screen_id')
        elements = node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        image_ref = _build_image_ref(node, include_images)
        summary = (node.get('summary') or '').strip()
        summary_suffix = f" 摘要:{summary}" if summary else ""

        bypass_edges = bypass_by_source.get(screen_id, [])
        bypass_hint = ""
        if bypass_edges:
            if len(bypass_edges) == 1:
                be = bypass_edges[0]
                btid = _safe_int(be.get('target'))
                btn = node_map.get(btid, {}) if btid is not None else {}
                bn = btn.get('screen_name', '弹窗')
                bypass_hint = (
                    f" [注意: 此步骤可能出现{bn}，"
                    f"需关闭弹窗后验证主流程页面元素仍可正常交互]"
                )
            else:
                bypass_items = []
                for bidx, be in enumerate(bypass_edges, 1):
                    btid = _safe_int(be.get('target'))
                    btn = node_map.get(btid, {}) if btid is not None else {}
                    bn = btn.get('screen_name', '弹窗')
                    bypass_items.append(f"{bidx}. {bn}")
                bypass_hint = (
                    f" [注意: 此步骤可能依次出现以下弹窗，需逐个关闭后验证主流程页面元素仍可正常交互: "
                    + "; ".join(bypass_items) + "]"
                )

        parts.append(
            f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}]"
            f" 元素: {element_desc}{image_ref}{summary_suffix}{bypass_hint}"
        )
    parts.append("")

    child_sources = {
        'branch': branch_by_source,
        'exception': exception_by_source,
    }
    child_labels = {'branch': '分支', 'exception': '异常'}
    child_categories = {'branch': 'boundary', 'exception': 'exception'}

    scene_idx = 2
    for i, node in enumerate(main_nodes, 1):
        screen_id = node.get('screen_id')
        source_name = node.get('screen_name', '')

        for ctype in ('branch', 'exception'):
            edges = child_sources[ctype].get(screen_id, [])
            for cidx, edge in enumerate(edges):
                tid = _safe_int(edge.get('target'))
                if tid is None:
                    continue
                target_node = node_map.get(tid, {})
                target_el_desc = _format_node_elements(
                    target_node.get('ui_spec_elements', []) or []
                )
                flow_meta = target_node.get('flow_meta') or {}
                img_ref = _build_image_ref(target_node, include_images)
                label = child_labels[ctype]
                condition = _infer_condition(edge, ctype, target_node, node)
                meta_hint = _render_flow_meta_hint(flow_meta, ctype)
                edge_hint = _render_edge_hint(edge)
                target_summary = (target_node.get('summary') or '').strip()
                target_summary_suffix = f" 摘要:{target_summary}" if target_summary else ""
                category = child_categories[ctype]

                parts.append(
                    f"### 场景{scene_idx}: {label}流程"
                    f"（源于步骤{i}[{source_name}]，case_category={category}）"
                )
                parts.append(
                    f"触发条件: {condition}{meta_hint}{edge_hint}"
                )
                parts.append(
                    f"起始点: 从步骤{i}[{source_name}]触发{label}，"
                    f"进入 [{target_node.get('screen_name', '')}]"
                )
                parts.append(
                    f"目标页面: [截图 - {target_node.get('screen_name', '')}]"
                    f" 元素: {target_el_desc}{img_ref}{target_summary_suffix}"
                )
                source_el_desc = _format_node_elements(node.get('ui_spec_elements', []) or [])
                source_key_elements = []
                if source_el_desc:
                    for el_part in source_el_desc.split(';')[:3]:
                        if ':' in el_part:
                            source_key_elements.append(el_part.split(':')[1].split('[')[0])
                elements_hint = '、'.join(source_key_elements) if source_key_elements else '页面已加载完成'
                parts.append(
                    f"用例要求: 仅验证此{label}场景，"
                    f"此用例依赖场景1（主干正向用例）执行到步骤{i}后的页面状态，"
                    f"depends_on 必须填写场景1的用例标题，anchor_step 必须填写{i}；"
                    f"前置条件只需写数据准备（如Mock接口返回值）和页面状态"
                    f"（如\"已处于{source_name}，可见{elements_hint}等元素\"），"
                    f"不需要重复描述到达路径（执行引擎会自动执行场景1到步骤{i}后继续）；"
                    f"步骤从触发{label}开始，预期结果聚焦{label}本身的表现"
                )
                parts.append("")
                scene_idx += 1

    bypass_edges_all = []
    for i, node in enumerate(main_nodes, 1):
        screen_id = node.get('screen_id')
        for edge in bypass_by_source.get(screen_id, []):
            tid = _safe_int(edge.get('target'))
            if tid is not None:
                bypass_edges_all.append((i, node, edge, tid))

    if bypass_edges_all:
        parts.append(
            f"### 场景{scene_idx}: 旁路流程（弹窗/浮层拦截，case_category=boundary）"
        )
        parts.append(
            "旁路说明: 旁路是主流程执行中自动弹出的干扰性弹窗或浮层，"
            "不需要为每个旁路单独生成用例，而是在主干正向用例的对应步骤中"
            "增加\"关闭弹窗\"操作即可。"
        )
        for i, node, edge, tid in bypass_edges_all:
            target_node = node_map.get(tid, {})
            condition = _infer_condition(edge, 'bypass', target_node, node)
            flow_meta = target_node.get('flow_meta') or {}
            meta_hint = _render_flow_meta_hint(flow_meta, 'bypass')
            edge_hint = _render_edge_hint(edge)
            parts.append(
                f"- 步骤{i}[{node.get('screen_name', '')}]: "
                f"{condition}{meta_hint}{edge_hint} → "
                f"关闭[{target_node.get('screen_name', '弹窗')}]后继续主流程"
            )
        parts.append("")

    parts.append("")
