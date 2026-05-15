"""辅助函数 - 流程图 Prompt 构建所需的工具函数。

提供:
    - _safe_int: 安全整数转换
    - _find_main_step: 主干步骤查找
    - _infer_condition: 触发条件自动推断
    - _render_flow_meta_hint: flow_meta 补充信息渲染
    - _group_edges_by_source: 按源节点分组连线
"""
from typing import List, Dict, Any, Optional

from loguru import logger


def _safe_int(value: Any) -> Optional[int]:
    """安全地将值转换为整数。

    Args:
        value: 待转换的值，支持 int/str 类型。

    Returns:
        转换后的整数，失败时返回 None。
    """
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"连线source/target格式错误: {value}")
        return None


def _find_main_step(main_nodes: List[Dict[str, Any]], screen_id: int) -> str:
    """在主干流程中查找指定 screen_id 对应的步骤序号。

    Args:
        main_nodes: 主干流程节点列表（已按 screen_order 排序）。
        screen_id: 待查找的屏幕 ID。

    Returns:
        步骤序号字符串，未找到时返回 '?'。
    """
    for i, node in enumerate(main_nodes, 1):
        if node.get('screen_id') == screen_id:
            return str(i)
    return '?'


_CONDITION_TEMPLATES = {
    'branch': '用户在{source_name}选择{target_name}相关操作',
    'exception': '{target_name}操作失败或系统异常',
    'bypass': '进入{source_name}时自动弹出{target_name}',
}


def _infer_condition(
    edge: Dict[str, Any],
    edge_type: str,
    target_node: Dict[str, Any],
    source_node: Optional[Dict[str, Any]] = None,
) -> str:
    """推断触发条件：优先使用用户填写的 condition，缺失时自动推断并标注来源。

    Args:
        edge: 连线数据，包含 condition/label 等字段。
        edge_type: 连线类型（branch/exception/bypass）。
        target_node: 目标节点数据，包含 screen_name 等字段。
        source_node: 源节点数据，包含 screen_name 等字段。缺失时回退到 edge.label。

    Returns:
        触发条件字符串，包含来源标注。
    """
    condition = (edge.get('condition') or '').strip()
    if condition:
        return f"{condition}（用户填写）"

    target_name = target_node.get('screen_name', '目标页面')
    raw_label = edge.get('label', '')
    if '：' in raw_label:
        clean_label = raw_label.split('：', 1)[-1].strip()
    elif ':' in raw_label:
        clean_label = raw_label.split(':', 1)[-1].strip()
    else:
        clean_label = raw_label.strip()
    source_name = (source_node or {}).get('screen_name') or clean_label or '当前页面'
    template = _CONDITION_TEMPLATES.get(edge_type)
    if template is None:
        logger.warning(
            f"未知 edge_type={edge_type}，无法推断条件"
            f" (edge={edge.get('id', '?')})"
        )
        return f"未知触发条件（edge_type={edge_type}）（系统推断）"
    inferred = template.format(source_name=source_name, target_name=target_name)
    logger.info(
        f"Auto-inferred {edge_type} condition: {inferred}"
        f" (edge={edge.get('id', '?')})"
    )
    return f"{inferred}（系统推断）"


def _render_flow_meta_hint(flow_meta: Dict[str, Any], edge_type: str) -> str:
    """渲染 flow_meta 中的补充信息为 Prompt 提示文本。

    Args:
        flow_meta: 节点的 flow_meta 数据，包含 pre_action/expected_result/bypass_reason/note。
        edge_type: 连线类型。

    Returns:
        补充提示字符串，无有效信息时返回空字符串。
    """
    hints = []

    pre_action = (flow_meta.get('pre_action') or '').strip()
    if pre_action:
        hints.append(f"前置操作: {pre_action}")

    expected_result = (flow_meta.get('expected_result') or '').strip()
    if expected_result:
        hints.append(f"预期结果: {expected_result}")

    bypass_reason = (flow_meta.get('bypass_reason') or '').strip()
    if edge_type == 'bypass' and bypass_reason:
        hints.append(f"旁路原因: {bypass_reason}")

    note = (flow_meta.get('note') or '').strip()
    if note:
        hints.append(f"备注: {note}")

    if not hints:
        return ''

    return f' [{"; ".join(hints)}]'


def _render_edge_hint(edge: Dict[str, Any]) -> str:
    """渲染连线中的 trigger_action/pre_action/note 为 Prompt 提示文本。

    与 _render_flow_meta_hint 的区别：
    - 本函数渲染连线级别的信息（触发动作、连线前置操作、连线备注）
    - _render_flow_meta_hint 渲染节点级别的信息（节点前置操作、节点预期结果等）

    Args:
        edge: 连线数据，包含 trigger_action/pre_action/note 字段。

    Returns:
        补充提示字符串，无有效信息时返回空字符串。
    """
    hints = []

    trigger_action = (edge.get('trigger_action') or '').strip()
    if trigger_action:
        hints.append(f"连线触发动作: {trigger_action}")

    pre_action = (edge.get('pre_action') or '').strip()
    if pre_action:
        hints.append(f"连线前置操作: {pre_action}")

    note = (edge.get('note') or '').strip()
    if note:
        hints.append(f"连线备注: {note}")

    if not hints:
        return ''

    return f' [{"; ".join(hints)}]'


def _group_edges_by_source(
    edge_list: List[Dict[str, Any]],
) -> Dict[int, List[Dict[str, Any]]]:
    """按源节点 screen_id 分组连线。

    Args:
        edge_list: 连线列表，每条连线包含 source 字段。

    Returns:
        以源节点 screen_id 为 key、连线列表为 value 的字典。
    """
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for e in edge_list:
        src = _safe_int(e.get('source'))
        if src is not None:
            grouped.setdefault(src, []).append(e)
    return grouped
