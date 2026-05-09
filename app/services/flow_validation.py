"""后端流程结构校验 - 对前端传递的 flow_sort_data 进行结构和逻辑校验。

M1B 阶段只记录 warning，不阻断生成。
M2 再考虑将错误返回前端展示。

校验规则：
    错误级别（M1B 仅记录，不阻断）：
        - graph 模式下 nodes 为空
        - 不存在主干节点
        - 分支/异常/旁路边缺少 target
        - edge 指向不存在的节点

    警告级别：
        - 多个主干节点但没有 normal 连线
        - 分支/异常缺少 condition 且无法自动推断
        - 存在孤立节点（无任何连线关联）
"""
from typing import List, Dict, Any, Tuple

from loguru import logger

from app.services.prompt_builder.helpers import _safe_int


def validate_flow_structure(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]]
) -> Tuple[List[str], List[str]]:
    """校验流程图数据结构，返回 (errors, warnings)。

    Args:
        nodes: 节点列表，每个节点包含 screen_id/flow_type/screen_name 等。
        edges: 连线列表，每条连线包含 source/target/edge_type/condition 等。

    Returns:
        (errors, warnings) 元组，errors 为错误列表，warnings 为警告列表。
    """
    errors: List[str] = []
    warnings: List[str] = []

    # 1. graph 模式下 nodes 为空
    if not nodes:
        errors.append('流程图节点列表为空')
        return errors, warnings

    # 2. 不存在主干节点
    main_nodes = [n for n in nodes if n.get('flow_type') == 'main']
    if not main_nodes:
        errors.append('流程图中不存在主干节点，至少需要一个主干节点')

    # Build node id set for lookup
    node_ids = set()
    for n in nodes:
        sid = n.get('screen_id')
        if sid is not None:
            node_ids.add(sid)

    # 3+4+6: Single pass over edges — missing target, nonexistent nodes, missing condition
    for edge in edges:
        edge_type = edge.get('edge_type', '')

        # 3. 所有连线缺少 target
        target = edge.get('target')
        if not target and target != 0:
            errors.append(
                f"{edge_type or '未知类型'}连线缺少 target (source={edge.get('source', '?')})"
            )

        # 4. edge 指向不存在的节点
        target_id = _safe_int(edge.get('target'))
        source_id = _safe_int(edge.get('source'))
        if target_id is not None and target_id not in node_ids:
            errors.append(
                f"连线 target={target_id} 指向不存在的节点 (source={edge.get('source', '?')})"
            )
        if source_id is not None and source_id not in node_ids:
            errors.append(
                f"连线 source={source_id} 指向不存在的节点 (target={edge.get('target', '?')})"
            )

        # 6. 分支/异常/旁路缺少 condition 且无法自动推断
        if edge_type in ('branch', 'exception', 'bypass'):
            condition = (edge.get('condition') or '').strip()
            if not condition:
                type_label_map = {'branch': '分支', 'exception': '异常', 'bypass': '旁路'}
                type_label = type_label_map.get(edge_type, '未知')
                warnings.append(
                    f"{type_label}连线 {edge.get('source', '?')} -> {edge.get('target', '?')} "
                    f"缺少触发条件，系统将自动推断"
                )

    # 5. 多个主干节点但没有 normal 连线
    if len(main_nodes) > 1:
        normal_edges = [e for e in edges if e.get('edge_type') == 'normal']
        if not normal_edges:
            warnings.append(
                '存在多个主干节点但没有正常连线，主干流程可能不完整'
            )

    # 7. 孤立节点（无任何连线关联）
    connected_ids = set()
    for edge in edges:
        src = _safe_int(edge.get('source'))
        tgt = _safe_int(edge.get('target'))
        if src is not None:
            connected_ids.add(src)
        if tgt is not None:
            connected_ids.add(tgt)
    for n in nodes:
        sid = n.get('screen_id')
        if sid is not None and sid not in connected_ids:
            warnings.append(
                f"节点 {sid} ({n.get('screen_name', '?')}) 是孤立节点，没有任何连线关联"
            )

    # Log results
    for e in errors:
        logger.error(f"[FlowValidation] ERROR: {e}")
    for w in warnings:
        logger.info(f"[FlowValidation] WARN: {w}")

    return errors, warnings
