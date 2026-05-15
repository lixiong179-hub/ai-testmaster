"""测试用例AI生成 - 辅助函数模块

本模块包含AI生成测试用例的共享辅助函数，供生成端点和流式端点复用。

函数概览:
    - _prepare_test_point: 从上下文中提取或构造测试点信息
    - _build_ui_specs_text: 将UI规格列表格式化为Prompt文本
    - _build_graph_prompt_data: 构建流程图模式所需的Prompt数据
    - _build_linear_prompt_data: 构建线性模式所需的Prompt数据
    - _format_case_response: 格式化生成的测试用例为响应数据
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import normalize_priority
from app.schemas.test_case import FlowSortDataSchema
from app.utils.test_case_helpers import convert_steps_to_response


def _prepare_test_point(
    context: Dict[str, Any], description: str, priority: int
) -> Dict[str, Any]:
    """从上下文中提取或构造测试点信息。"""
    test_points = context.get("test_points", [])
    test_point = context.get("test_point", {}) or context.get("current_test_point", {})
    if not test_point and test_points:
        test_point = test_points[0]
    if not test_point:
        test_point = {
            "module": context.get("module", "未知模块"),
            "function": context.get("function") or context.get("point", ""),
            "point": context.get("point", "未知测试点"),
            "priority": priority,
        }
    return test_point


def _build_ui_specs_text(ui_specs: List[Dict[str, Any]]) -> str:
    """将UI规格列表格式化为Prompt文本。"""
    if not ui_specs:
        return ""
    from app.services.prompt_builder import format_ui_spec_for_prompt
    spec_parts = []
    for spec_item in ui_specs:
        screen_name = spec_item.get("screen_name", "未命名页面")
        spec = spec_item.get("ui_spec", {})
        if spec:
            spec_parts.append(format_ui_spec_for_prompt(screen_name, spec))
    return "\n\n".join(spec_parts) if spec_parts else ""


def _build_graph_prompt_data(
    flow_sort_data: FlowSortDataSchema,
    context: Dict[str, Any], description: str, priority: int,
    case_type: Optional[str] = None,
) -> Dict[str, Any]:
    """构建流程图模式所需的Prompt数据。"""
    from app.services.prompt_builder import PromptBuilder
    from app.services.flow_validation import validate_flow_structure
    nodes_list = [n.model_dump() for n in flow_sort_data.nodes]
    edges_list = [e.model_dump() for e in flow_sort_data.edges]

    # 后端流程结构校验（错误时阻断，警告仅记录）
    errors, warnings = validate_flow_structure(nodes_list, edges_list)
    if errors:
        error_msg = f"流程图结构校验失败: {'; '.join(errors[:5])}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    if warnings:
        logger.info(f"流程图校验发现 {len(warnings)} 个警告: {warnings}")
    module_info = flow_sort_data.module_info
    test_point = _prepare_test_point(context, description, priority)
    ui_specs = context.get("ui_specs", [])
    ui_specs_text = _build_ui_specs_text(ui_specs)
    test_point_json = json.dumps(test_point, ensure_ascii=False)
    history_cases = context.get("history_cases")
    graph_prompt = PromptBuilder.build_graph_prompt(
        nodes=nodes_list, edges=edges_list, module_info=module_info,
        requirement_content=context.get("requirement_content", ""),
        test_point_json=test_point_json, ui_specs_text=ui_specs_text,
        history_cases=history_cases, case_type=case_type,
    )
    logger.info(f"流程图模式：接收到 {len(nodes_list)} 个节点，{len(edges_list)} 条连线")
    return {
        "requirement_content": context.get("requirement_content", ""),
        "ui_description": "",
        "ui_spec": ui_specs[0].get("ui_spec", {}) if ui_specs else {},
        "ui_specs": ui_specs, "test_point": test_point,
        "case_type": case_type or context.get("case_type"),
        "exec_mode": context.get("exec_mode", "all"),
        "project_config": context.get("project_config"),
        "graph_prompt": graph_prompt,
        "flow_validation": {"errors": errors, "warnings": warnings},
    }


def _build_linear_prompt_data(
    context: Dict[str, Any], description: str, priority: int,
    case_type: Optional[str], exec_mode: str,
) -> Dict[str, Any]:
    """构建线性模式所需的Prompt数据。"""
    test_point = _prepare_test_point(context, description, priority)
    raw_ui_desc = context.get("ui_description", "")
    ui_specs = context.get("ui_specs", [])
    return {
        "requirement_content": context.get("requirement_content", ""),
        "ui_description": raw_ui_desc,
        "ui_spec": ui_specs[0].get("ui_spec", {}) if ui_specs else {},
        "ui_specs": ui_specs, "test_point": test_point,
        "case_type": case_type, "exec_mode": exec_mode,
        "project_config": context.get("project_config"),
        "history_cases": context.get("history_cases"),
    }


def _format_case_response(
    generated_case: Dict[str, Any], project_id: int,
    description: str, priority: int, case_type: Optional[str],
) -> Dict[str, Any]:
    """格式化生成的测试用例为响应数据。"""
    if not isinstance(generated_case, dict):
        raise TypeError(
            f"_format_case_response 期望 generated_case 为 dict，实际类型: {type(generated_case).__name__}"
        )
    ai_priority = generated_case.get("priority")
    priority = normalize_priority(ai_priority) if ai_priority is not None else priority
    steps_data = convert_steps_to_response(generated_case.get("steps", []))
    return {
        "id": 0, "project_id": project_id,
        "case_no": f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "module": generated_case.get("module", "AI生成"),
        "title": generated_case.get("title", description[:50]),
        "precondition": generated_case.get("precondition", ""),
        "test_data": generated_case.get("test_data", {}),
        "steps": steps_data,
        "expected_result": generated_case.get("expected_result", ""),
        "priority": priority,
        "case_type": generated_case.get("case_type", case_type),
        "test_category": generated_case.get("test_category") or generated_case.get("case_category", ""),
        "case_category": generated_case.get("case_category", ""),
        "change_type": generated_case.get("change_type", "added"),
        "parent_case_id": generated_case.get("parent_case_id"),
        "generate_status": 1,
        "create_time": datetime.now().isoformat(),
    }
