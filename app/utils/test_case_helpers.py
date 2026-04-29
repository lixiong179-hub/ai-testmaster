"""
测试用例通用工具函数

提供统一的步骤转换、响应构建等功能，避免代码重复
"""
from typing import Optional, List, Dict, Any
from datetime import datetime


def _build_step_response(step: Dict, step_number: Optional[int] = None) -> Dict[str, Any]:
    """
    构建单个步骤的响应格式（内部辅助函数）

    Args:
        step: 步骤字典
        step_number: 步骤序号（可选）

    Returns:
        标准化的步骤字典
    """
    action = step.get("action", step.get("step", step.get("description", "执行")))

    response = {
        "step": action,
        "action": action,
        "param": step.get("param", ""),
        "test_data": step.get("test_data", {}),
        "expected_result": step.get("expected_result", ""),
        "action_type": step.get("action_type", ""),
        "input_value": step.get("input_value", ""),
        "target_element": step.get("target_element", ""),
    }

    if step_number is not None:
        response["step_number"] = step_number
    elif "step_number" in step:
        response["step_number"] = step["step_number"]

    return response


def convert_steps_to_response(steps_json: Optional[List[Dict]]) -> List[Dict[str, Any]]:
    """
    将数据库steps_json转换为API响应格式

    统一处理不同格式的步骤数据，确保输出格式一致

    Args:
        steps_json: 数据库中的步骤JSON数据

    Returns:
        标准化的步骤列表
    """
    if not steps_json:
        return []

    result = []
    for i, step in enumerate(steps_json):
        step_number = step.get("step_number", i + 1)
        result.append(_build_step_response(step, step_number))

    return result


def build_test_case_response(test_case) -> Dict[str, Any]:
    """
    构建统一的测试用例响应格式

    Args:
        test_case: TestCase模型实例

    Returns:
        标准化的测试用例字典
    """
    create_time = getattr(test_case, 'create_time', None)
    if create_time and isinstance(create_time, datetime):
        create_time = create_time.isoformat()

    return {
        "id": test_case.id,
        "project_id": test_case.project_id,
        "case_no": getattr(test_case, 'case_no', ''),
        "module": getattr(test_case, 'module', ''),
        "title": test_case.title,
        "precondition": getattr(test_case, 'precondition', ''),
        "steps": convert_steps_to_response(getattr(test_case, 'steps_json', None)),
        "expected_result": getattr(test_case, 'expected_result', ''),
        "priority": test_case.priority,
        "case_type": getattr(test_case, 'case_type', ''),
        "test_category": getattr(test_case, 'test_category', None),
        "exec_script": getattr(test_case, 'exec_script', ''),
        "generate_status": getattr(test_case, 'generate_status', 0),
        "create_time": create_time
    }


def convert_ai_steps_to_response(steps: List[Dict]) -> List[Dict[str, Any]]:
    """
    转换AI生成的步骤数据为标准格式

    处理AI返回的各种步骤格式，统一转换为标准响应格式

    Args:
        steps: AI生成的步骤列表

    Returns:
        标准化的步骤列表
    """
    return [_build_step_response(step) for step in steps]
