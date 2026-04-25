"""测试用例生成 Prompt 构建 - 流程图模式。

提供:
    - _build_graph_prompt: 流程图模式 Prompt 构建
"""
from typing import List, Dict, Any, Optional

from loguru import logger

from app.services.prompt_builder.helpers import _safe_int, _find_main_step


def _build_graph_prompt(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    module_info: Optional[Dict[str, Any]] = None,
    requirement_content: str = "",
    test_point_json: str = "",
    ui_specs_text: str = "",
    include_images: bool = False
) -> str:
    """构建流程图模式的 Prompt。

    Prompt 结构:
        1. 角色设定（资深测试工程师）
        2. 测试点信息（JSON 格式）
        3. 需求文档内容
        4. UI 原型图解析结果
        5. UI 原型图流程结构（主干/分支/异常/旁路）
        6. 输出格式要求

    Args:
        nodes: 节点列表，每个节点包含 screen_id/screen_order/flow_type 等。
        edges: 连线列表，每条连线包含 source/target/edge_type/condition 等。
        module_info: 模块基础信息，包含 name 和 description。
        requirement_content: 需求文档内容。
        test_point_json: 测试点 JSON 字符串。
        ui_specs_text: UI 规格格式化文本。
        include_images: 是否在 Prompt 中包含图片 URL。

    Returns:
        完整的 Prompt 字符串。
    """
    node_map = {n.get('screen_id'): n for n in nodes}
    main_nodes = sorted(
        [n for n in nodes if n.get('flow_type') == 'main'],
        key=lambda n: (
            n.get('main_order') or n.get('screen_order', 0),
            n.get('screen_order', 0)
        )
    )

    branch_edges = [e for e in edges if e.get('edge_type') == 'branch']
    exception_edges = [e for e in edges if e.get('edge_type') == 'exception']
    bypass_edges = [e for e in edges if e.get('edge_type') == 'bypass']

    parts = []
    parts.append("你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下多源信息生成详细的、可执行的测试用例。\n")

    if test_point_json:
        parts.append(f"## 测试点信息\n{test_point_json}\n")

    if requirement_content and requirement_content.strip():
        parts.append(f"## 需求文档内容\n{requirement_content}\n")
    else:
        parts.append("## 需求文档内容\n[无需求文档内容]\n")

    if module_info:
        parts.append("## 模块信息")
        parts.append(module_info.get('name', ''))
        parts.append(module_info.get('description', ''))
        parts.append("")

    if ui_specs_text:
        parts.append(f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_specs_text}\n")

    _append_main_flow(parts, main_nodes, include_images)
    _append_branch_flow(parts, branch_edges, node_map, main_nodes, include_images)
    _append_exception_flow(parts, exception_edges, node_map, main_nodes, include_images)
    _append_bypass_flow(parts, bypass_edges, node_map, main_nodes, include_images)
    _append_generation_rules(parts)

    return "\n".join(parts)


def _format_node_elements(elements: Optional[List[Dict[str, Any]]]) -> str:
    """格式化节点的 UI 元素列表为简短描述。

    Args:
        elements: UI 元素列表。

    Returns:
        逗号分隔的元素描述字符串。
    """
    if not elements:
        return ""
    return ', '.join(
        [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
    )


def _build_image_ref(node: Dict[str, Any], include_images: bool) -> str:
    """构建节点的图片 URL 引用文本。

    Args:
        node: 节点字典，需包含 image_url 字段。
        include_images: 是否包含图片 URL。

    Returns:
        图片 URL 引用文本，不包含时返回空字符串。
    """
    if include_images and node.get('image_url'):
        return f" [图片URL: {node.get('image_url', '')}]"
    return ""


def _append_main_flow(
    parts: List[str],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加主干流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    parts.append("## UI原型图流程结构\n")
    parts.append("### 主干流程（按顺序执行，必须完整覆盖）")
    for i, node in enumerate(main_nodes, 1):
        elements = node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        image_ref = _build_image_ref(node, include_images)
        parts.append(f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}] 元素: {element_desc}{image_ref}")
    parts.append("")


def _append_branch_flow(
    parts: List[str],
    branch_edges: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加分支流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        branch_edges: 分支连线列表。
        node_map: 节点映射字典。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    if not branch_edges:
        return
    parts.append("### 分支流程（满足条件时执行，每个分支作为独立测试场景）")
    for idx, edge in enumerate(branch_edges):
        target_screen_id = _safe_int(edge.get('target'))
        source_screen_id = _safe_int(edge.get('source'))
        if target_screen_id is None or source_screen_id is None:
            continue
        target_node = node_map.get(target_screen_id, {})
        source_step = _find_main_step(main_nodes, source_screen_id)
        elements = target_node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        trigger_condition = (edge.get('condition') or '').strip()
        if not trigger_condition:
            logger.warning(f"branch edge missing condition: {edge}")
            trigger_condition = '未指定'
        image_ref = _build_image_ref(target_node, include_images)
        parts.append(
            f"分支 {chr(ord('A') + idx)}: 从步骤 {source_step} 分支，"
            f"触发条件「{trigger_condition}」"
        )
        parts.append(
            f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
        )
    parts.append("")


def _append_exception_flow(
    parts: List[str],
    exception_edges: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加异常流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        exception_edges: 异常连线列表。
        node_map: 节点映射字典。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    if not exception_edges:
        return
    parts.append("### 异常流程（异常场景下触发，需标注异常场景和预期错误提示）")
    for idx, edge in enumerate(exception_edges):
        target_screen_id = _safe_int(edge.get('target'))
        source_screen_id = _safe_int(edge.get('source'))
        if target_screen_id is None or source_screen_id is None:
            continue
        target_node = node_map.get(target_screen_id, {})
        source_step = _find_main_step(main_nodes, source_screen_id)
        elements = target_node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        exception_condition = (edge.get('condition') or '').strip()
        if not exception_condition:
            logger.warning(f"exception edge missing condition: {edge}")
            exception_condition = '未指定'
        image_ref = _build_image_ref(target_node, include_images)
        parts.append(
            f"异常 {chr(ord('A') + idx)}: 从步骤 {source_step} 异常跳转，"
            f"异常场景「{exception_condition}」"
        )
        parts.append(
            f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
        )
    parts.append("")


def _append_bypass_flow(
    parts: List[str],
    bypass_edges: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    main_nodes: List[Dict[str, Any]],
    include_images: bool
) -> None:
    """追加旁路流程描述到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        bypass_edges: 旁路连线列表。
        node_map: 节点映射字典。
        main_nodes: 主干流程节点列表。
        include_images: 是否包含图片 URL。
    """
    if not bypass_edges:
        return
    parts.append("### 旁路流程（出现时机和关闭方式，不影响主流程）")
    for idx, edge in enumerate(bypass_edges):
        target_screen_id = _safe_int(edge.get('target'))
        source_screen_id = _safe_int(edge.get('source'))
        if target_screen_id is None or source_screen_id is None:
            continue
        target_node = node_map.get(target_screen_id, {})
        source_step = _find_main_step(main_nodes, source_screen_id)
        condition = (edge.get('condition') or '').strip()
        if not condition:
            logger.warning(f"bypass edge missing condition: {edge}")
            condition = '自动弹出'
        elements = target_node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        image_ref = _build_image_ref(target_node, include_images)
        parts.append(
            f"旁路 {chr(ord('A') + idx)}: 进入步骤 {source_step} 时"
            f"{condition}，关闭后继续主流程"
        )
        parts.append(
            f"  → [截图 - {target_node.get('screen_name', '')}] 元素: {element_desc}{image_ref}"
        )
    parts.append("")


def _append_generation_rules(parts: List[str]) -> None:
    """追加生成要求和输出格式到 parts 列表。

    Args:
        parts: Prompt 片段列表。
    """
    parts.append("## 生成要求")
    parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
    parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
    parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
    parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
    parts.append("5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；若未提供，仅根据UI原型图推断业务逻辑")
    parts.append("6. 若提供了测试点，优先覆盖测试点中的测试维度；若未提供，根据UI元素自动生成测试点")
    parts.append("7. 只输出JSON格式内容，不要添加任何其他文字")

    parts.append("""
## 输出JSON格式：
{
  "title": "用例标题",
  "module": "模块名称",
  "precondition": "前置条件",
  "test_data": {"normal": {}, "boundary": {}, "abnormal": {}},
  "steps": [
    {"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}
  ],
  "expected_result": "总体预期结果",
  "case_type": "ui_automation",
  "case_category": "ui_automation",
  "priority": 2
}""")

