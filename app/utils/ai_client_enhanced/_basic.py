import re
from typing import Any, Dict, List, Optional

from app.utils.ai_client_parser import infer_action_type
from app.utils.ai_client_enhanced._enhanced import generate_test_case_enhanced


def generate_test_case(test_point: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(test_point, str):
        test_point = {"point": test_point, "module": "未知模块", "function": "未知功能", "priority": 2}
    if context:
        context['test_points'] = [test_point]
        result = generate_test_case_enhanced(context)
        return result[0] if result else {}
    from app.utils.ai_client_core import AIClientBase
    from app.utils.ai_client_test_case import AITestCaseMixin
    class _TempClient(AITestCaseMixin, AIClientBase):
        pass
    client = _TempClient()
    return client.generate_test_case(test_point)


async def analyze_requirements_stream(content: str) -> Any:
    from app.utils.ai_client_core import AIClientBase
    from app.utils.ai_client_stream import AIStreamMixin
    class _TempClient(AIStreamMixin, AIClientBase):
        pass
    client = _TempClient()
    async for chunk in client.analyze_requirements_stream(content):
        yield chunk


async def generate_test_case_stream(test_point: Dict[str, Any]) -> Any:
    from app.utils.ai_client_core import AIClientBase
    from app.utils.ai_client_stream import AIStreamMixin
    class _TempClient(AIStreamMixin, AIClientBase):
        pass
    client = _TempClient()
    async for chunk in client.generate_test_case_stream(test_point):
        yield chunk


def parse_precondition_to_steps(precondition: str) -> List[Dict[str, Any]]:
    if not precondition or not precondition.strip():
        return []
    steps = []
    precondition = precondition.strip()
    patterns = [
        r'(?:步骤\s*)?(\d+)[.、)\]]\s*(.+?)(?=(?:步骤\s*)?\d+[.、)\]]|$)',
        r'(\d+)\.\s*(.+?)(?=\d+\.|$)',
    ]
    matched = False
    for pattern in patterns:
        matches = re.findall(pattern, precondition, re.DOTALL)
        if matches and len(matches) > 1:
            for step_num, step_text in matches:
                step_text = step_text.strip()
                if step_text:
                    action_type = infer_action_type(step_text)
                    steps.append({
                        'step': int(step_num) if step_num.isdigit() else len(steps) + 1,
                        'action': step_text, 'action_type': action_type,
                        'input_value': '', 'target_element': '',
                        'description': f'{len(steps) + 1}. {step_text}',
                        'expected_result': f'{step_text}完成',
                        'test_data': [], 'ui_elements': []
                    })
            matched = True
            break
    if not matched:
        line_pattern = r'[;；\n]+'
        lines = re.split(line_pattern, precondition)
        lines = [line.strip() for line in lines if line.strip()]
        if len(lines) > 1:
            for i, line in enumerate(lines):
                action_type = infer_action_type(line)
                steps.append({
                    'step': i + 1, 'action': line, 'action_type': action_type,
                    'input_value': '', 'target_element': '',
                    'description': f'{i + 1}. {line}',
                    'expected_result': f'{line}完成',
                    'test_data': [], 'ui_elements': []
                })
        else:
            action_type = infer_action_type(precondition)
            steps.append({
                'step': 1, 'action': precondition, 'action_type': action_type,
                'input_value': '', 'target_element': '',
                'description': f'1. {precondition}',
                'expected_result': f'{precondition}完成',
                'test_data': [], 'ui_elements': []
            })
    return steps
