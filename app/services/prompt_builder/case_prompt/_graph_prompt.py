from typing import List, Dict, Any, Optional

from loguru import logger

from app.services.prompt_builder.helpers import (
    _safe_int,
    _infer_condition,
    _render_flow_meta_hint,
    _render_edge_hint,
    _group_edges_by_source,
)
from app.services.prompt_builder.flow_aware_history import (
    _append_flow_aware_history_cases,
)
from app.services.prompt_builder.comparison_examples import (
    get_comparison_examples,
    get_title_spec_rules,
    get_precondition_spec_rules,
    get_automation_friendly_rules,
)
from app.services.prompt_builder.case_prompt._flow_builder import _append_nested_flow
from app.services.prompt_builder.case_prompt._rules import _append_generation_rules
from app.services.prompt_builder.case_prompt._node_format import (
    _format_node_elements,
    _build_image_ref,
)


def _build_graph_prompt(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    module_info: Optional[Dict[str, Any]] = None,
    requirement_content: str = "",
    test_point_json: str = "",
    ui_specs_text: str = "",
    include_images: bool = False,
    history_cases: Optional[List[Dict[str, Any]]] = None,
    case_type: Optional[str] = None,
    test_username: str = "testuser",
    test_password: str = "TestPass123",
    min_case_count: int = 3,
) -> str:
    node_map: Dict[Any, Dict[str, Any]] = {}
    for n in nodes:
        sid = n.get('screen_id')
        if sid in node_map:
            logger.warning(f"重复 screen_id={sid}，后者覆盖前者")
        node_map[sid] = n

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

    branch_by_source = _group_edges_by_source(branch_edges)
    exception_by_source = _group_edges_by_source(exception_edges)
    bypass_by_source = _group_edges_by_source(bypass_edges)

    parts = []
    parts.append(
        "你是一名资深测试工程师，拥有10年以上的测试经验。"
        "请根据以下多源信息生成详细的、可执行的测试用例。\n"
    )

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

    _append_nested_flow(
        parts, main_nodes, node_map,
        branch_by_source, exception_by_source, bypass_by_source, include_images
    )

    if history_cases:
        _append_flow_aware_history_cases(
            parts, history_cases, main_nodes,
            branch_by_source, exception_by_source, bypass_by_source, node_map
        )

    _append_generation_rules(parts, case_type, has_history=bool(history_cases), min_case_count=min_case_count)

    prompt = "\n".join(parts)
    if test_username != "admin":
        prompt = prompt.replace("admin", test_username)
    if test_password != "Admin123":
        prompt = prompt.replace("Admin123", test_password)

    return prompt



