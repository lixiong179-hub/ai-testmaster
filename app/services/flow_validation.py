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

from typing import Any

from loguru import logger

from app.services.prompt_builder.helpers import _safe_int


#: 需要触发「缺少触发条件」告警的连线类型 → 中文标签。
_CONDITION_REQUIRED_EDGE_LABELS = {"branch": "分支", "exception": "异常", "bypass": "旁路"}


def _collect_node_ids(nodes: list[dict[str, Any]]) -> set:
    """收集节点 screen_id 集合（None 跳过）。"""
    node_ids = set()
    for n in nodes:
        sid = n.get("screen_id")
        if sid is not None:
            node_ids.add(sid)
    return node_ids


def _validate_main_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """主干节点存在性，以及多主干但无 normal 连线的告警。"""
    errors: list[str] = []
    warnings: list[str] = []

    main_nodes = [n for n in nodes if n.get("flow_type") == "main"]
    if not main_nodes:
        errors.append("流程图中不存在主干节点，至少需要一个主干节点")

    if len(main_nodes) > 1:
        normal_edges = [e for e in edges if e.get("edge_type") == "normal"]
        if not normal_edges:
            warnings.append("存在多个主干节点但没有正常连线，主干流程可能不完整")
    return errors, warnings


def _validate_edge_endpoints(edge: dict[str, Any], node_ids: set) -> list[str]:
    """连线 target 缺失、source/target 指向不存在节点。"""
    errors: list[str] = []
    edge_type = edge.get("edge_type", "")

    target = edge.get("target")
    if not target and target != 0:
        errors.append(f"{edge_type or '未知类型'}连线缺少 target (source={edge.get('source', '?')})")

    target_id = _safe_int(edge.get("target"))
    source_id = _safe_int(edge.get("source"))
    if target_id is not None and target_id not in node_ids:
        errors.append(f"连线 target={target_id} 指向不存在的节点 (source={edge.get('source', '?')})")
    if source_id is not None and source_id not in node_ids:
        errors.append(f"连线 source={source_id} 指向不存在的节点 (target={edge.get('target', '?')})")
    return errors


def _validate_edge_condition(edge: dict[str, Any]) -> list[str]:
    """分支/异常/旁路连线缺触发条件时给出告警。"""
    edge_type = edge.get("edge_type", "")
    if edge_type not in _CONDITION_REQUIRED_EDGE_LABELS:
        return []
    condition = (edge.get("condition") or "").strip()
    if condition:
        return []
    type_label = _CONDITION_REQUIRED_EDGE_LABELS.get(edge_type, "未知")
    return [f"{type_label}连线 {edge.get('source', '?')} -> {edge.get('target', '?')} 缺少触发条件，系统将自动推断"]


def _validate_edges(edges: list[dict[str, Any]], node_ids: set) -> tuple[list[str], list[str]]:
    """单遍扫描连线：端点错误 + 条件缺失告警。"""
    errors: list[str] = []
    warnings: list[str] = []
    for edge in edges:
        errors.extend(_validate_edge_endpoints(edge, node_ids))
        warnings.extend(_validate_edge_condition(edge))
    return errors, warnings


def _collect_connected_ids(edges: list[dict[str, Any]]) -> set:
    """收集所有连线涉及的 source/target 节点 ID。"""
    connected_ids = set()
    for edge in edges:
        src = _safe_int(edge.get("source"))
        tgt = _safe_int(edge.get("target"))
        if src is not None:
            connected_ids.add(src)
        if tgt is not None:
            connected_ids.add(tgt)
    return connected_ids


def _collect_orphan_warnings(nodes: list[dict[str, Any]], connected_ids: set) -> list[str]:
    """无任何连线关联的节点告警。"""
    warnings: list[str] = []
    for n in nodes:
        sid = n.get("screen_id")
        if sid is not None and sid not in connected_ids:
            warnings.append(f"节点 {sid} ({n.get('screen_name', '?')}) 是孤立节点，没有任何连线关联")
    return warnings


def _log_validation_result(errors: list[str], warnings: list[str]) -> None:
    """按级别输出校验结果日志。"""
    for e in errors:
        logger.error(f"[FlowValidation] ERROR: {e}")
    for w in warnings:
        logger.info(f"[FlowValidation] WARN: {w}")


def validate_flow_structure(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """校验流程图数据结构，返回 (errors, warnings)。

    Args:
        nodes: 节点列表，每个节点包含 screen_id/flow_type/screen_name 等。
        edges: 连线列表，每条连线包含 source/target/edge_type/condition 等。

    Returns:
        (errors, warnings) 元组，errors 为错误列表，warnings 为警告列表。
    """
    # 1. graph 模式下 nodes 为空
    if not nodes:
        return ["流程图节点列表为空"], []

    node_ids = _collect_node_ids(nodes)
    main_errors, main_warnings = _validate_main_nodes(nodes, edges)
    edge_errors, edge_warnings = _validate_edges(edges, node_ids)
    orphan_warnings = _collect_orphan_warnings(nodes, _collect_connected_ids(edges))

    # 顺序对齐历史行为：主干错误 → 连线错误；连线告警 → 主干告警 → 孤立节点告警
    errors = main_errors + edge_errors
    warnings = edge_warnings + main_warnings + orphan_warnings

    _log_validation_result(errors, warnings)
    return errors, warnings
