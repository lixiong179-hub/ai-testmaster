import re
from typing import Dict, Any, List
from loguru import logger

from app.utils.ai_client_parser import (
    infer_test_category,
    infer_action_type,
    extract_input_value_from_expected,
)


def normalize_new_format(case: Dict[str, Any]) -> Dict[str, Any]:
    steps = case.get('steps', [])
    expected_results = case.get('expected_results', [])
    normalized_steps = []
    for i, step in enumerate(steps):
        action_type = step.get('action_type', '')
        if not action_type:
            action_type = infer_action_type(step.get('action', ''))
        input_value = step.get('input_value', '')
        expected_result = expected_results[i] if i < len(expected_results) else ''
        step_expected = step.get('expected_result', '')
        if not expected_result and step_expected:
            expected_result = step_expected
        if action_type == 'input' and not input_value:
            extracted, cleaned = extract_input_value_from_expected(expected_result)
            if extracted:
                input_value = extracted
                expected_result = cleaned
        if not input_value and action_type in ('input', 'select'):
            action_text = step.get('action', '')
            match = re.search(r"(?:输入|填写)[：:]?\s*['\"']([^'\"]+)['\"']", action_text)
            if not match:
                match = re.search(r"选择\s*['\"']([^'\"]+)['\"']", action_text)
            if match:
                input_value = match.group(1)
        normalized_steps.append({
            'step': step.get('step', str(i + 1)),
            'action': step.get('action', ''),
            'action_type': action_type,
            'input_value': input_value,
            'target_element': step.get('target_element', ''),
            'description': f"{step.get('step', i + 1)}. {step.get('action', '')}",
            'expected_result': expected_result,
            'test_data': [],
            'ui_elements': []
        })

    def _add_step_number(text: str, idx: int) -> str:
        stripped = text.strip()
        if re.match(r'^\d+\.\s+', stripped) or (stripped.startswith('【') and '】' in stripped):
            return stripped
        return f"{idx + 1}. {stripped}"

    overall_expected = chr(10).join(
        [_add_step_number(r, i) for i, r in enumerate(expected_results)]
    ) if expected_results else chr(10).join(
        [_add_step_number(s.get('expected_result', ''), i) for i, s in enumerate(steps) if s.get('expected_result')]
    )
    case_type = case.get('case_type', '')
    test_category = case.get('test_category')
    legacy_case_types = ('功能测试', '功能', 'UI', 'API', '接口', '接口测试', 'functional', 'api_auto', 'compatibility')
    if case_type in legacy_case_types or case_type == '' or case_type is None or not test_category:
        inferred_case_type, inferred_test_category = infer_test_category(steps)
        if case_type in legacy_case_types or case_type == '' or case_type is None:
            case_type = inferred_case_type
        if not test_category:
            test_category = inferred_test_category
    valid_types = ('ui_automation', 'manual', 'api_automation', 'performance', 'security')
    if case_type not in valid_types:
        from app.core.constants import TestCaseType
        case_type = TestCaseType.from_legacy(case_type).value
    if test_category not in valid_types:
        test_category = case_type
    return {
        'title': case.get('title', ''),
        'module': case.get('module', ''),
        'precondition': case.get('precondition', ''),
        'case_type': case_type,
        'test_category': test_category,
        'priority': case.get('priority', 'P2'),
        'expected_result': overall_expected or case.get('expected_result', ''),
        'test_data': {},
        'steps': normalized_steps
    }


def normalize_old_format(case: Dict[str, Any]) -> Dict[str, Any]:
    priority = case.get('priority', 2)
    if priority == 1 or priority == '1':
        priority_str = 'P0'
    elif priority == 3 or priority == '3':
        priority_str = 'P3'
    else:
        priority_str = 'P2'
    raw_steps = case.get('steps', [])
    normalized_steps = []
    for i, step in enumerate(raw_steps):
        action = step.get('action', step.get('description', ''))
        action_type = infer_action_type(action)
        input_value = ''
        if action_type == 'input':
            m = re.search(r'[输入填写录入键入]\s*[""\u201c]?(.+?)[""\u201d]?(?:为|：|:|$)', action)
            if m:
                input_value = m.group(1).strip()
            step_expected = step.get('expected_result', '')
            if not input_value and step_expected:
                extracted, _ = extract_input_value_from_expected(step_expected)
                if extracted:
                    input_value = extracted
        target_element = ''
        elem_match = re.search(r'[""\u201c](.+?)[""\u201d]', action)
        if elem_match:
            target_element = elem_match.group(1).strip()
        normalized_steps.append({
            'step': step.get('step', i + 1),
            'action': action,
            'action_type': action_type,
            'input_value': input_value,
            'target_element': target_element,
            'description': step.get('description', f"【{step.get('step', i + 1)}】{action}"),
            'expected_result': step.get('expected_result', ''),
            'test_data': step.get('test_data', []),
            'ui_elements': step.get('ui_elements', [])
        })
    case_type = case.get('case_type', '')
    test_category = case.get('test_category')
    legacy_case_types = ('功能测试', '功能', 'UI', 'API', '接口', '接口测试', 'functional', 'api_auto', 'compatibility')
    if case_type in legacy_case_types or case_type == '' or case_type is None or not test_category:
        inferred_case_type, inferred_test_category = infer_test_category(raw_steps)
        if case_type in legacy_case_types or case_type == '' or case_type is None:
            case_type = inferred_case_type
        if not test_category:
            test_category = inferred_test_category
    valid_types = ('ui_automation', 'manual', 'api_automation', 'performance', 'security')
    if case_type not in valid_types:
        from app.core.constants import TestCaseType
        case_type = TestCaseType.from_legacy(case_type).value
    if test_category not in valid_types:
        test_category = case_type
    return {
        'title': case.get('title', ''),
        'module': case.get('module', ''),
        'precondition': case.get('precondition', ''),
        'case_type': case_type,
        'test_category': test_category,
        'priority': priority_str,
        'expected_result': case.get('expected_result', ''),
        'test_data': case.get('test_data', {}),
        'steps': normalized_steps
    }
