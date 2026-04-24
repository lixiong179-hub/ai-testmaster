import requests
import json
import re
import time
from typing import Dict, Any, Optional, List
from loguru import logger

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
    _detect_ai_error,
    get_ai_client,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    infer_test_category,
    infer_action_type,
    extract_input_value_from_expected,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)


def generate_test_case_enhanced(context: Dict[str, Any]) -> Dict[str, Any]:
    graph_prompt = context.get('graph_prompt')
    if graph_prompt:
        prompt = graph_prompt
    else:
        from app.utils.ai_client_prompt import (
            sanitize_input, build_weight_model,
            build_ui_specs_description, build_project_env_info
        )
        requirement = sanitize_input(context.get('requirement', ''))
        test_points = context.get('test_points', [])
        ui_specs = context.get('ui_specs', [])
        project_config = context.get('project_config', {})
        has_requirement = bool(requirement and requirement.strip())
        has_ui = bool(ui_specs)
        has_test_point = bool(test_points)
        weight_desc, weight_example, weight_warning = build_weight_model(has_requirement, has_ui, has_test_point)
        ui_desc = build_ui_specs_description(ui_specs) if has_ui else "无UI原型图解析结果"
        env_desc = build_project_env_info(project_config)
        test_points_text = ""
        if test_points:
            test_points_text = "## 测试点列表\n"
            for i, tp in enumerate(test_points):
                module = tp.get('module', '')
                function = tp.get('function', '')
                point = tp.get('point', '')
                priority = tp.get('priority', 2)
                test_points_text += f"{i+1}. [{module} - {function}] {point} (优先级:{priority})\n"
        prompt = f"""你是一名高级测试工程师，请根据以下信息生成一个高质量的测试用例。

{weight_desc}

{weight_example}

{weight_warning}

---

## 需求文档
{requirement if has_requirement else "（未提供需求文档）"}

---

## UI原型图解析结果
{ui_desc}

---

{test_points_text}

---

{env_desc}

---

## 输出格式要求
请严格按照以下JSON格式输出（不要添加markdown代码块标记）：
{{
  "title": "用例标题（简洁明确，包含测试目标）",
  "module": "所属模块",
  "precondition": "系统已通过配置自动登录至目标页面",
  "case_type": "ui_automation/manual/api_automation/performance/security",
  "test_category": "与case_type保持一致",
  "priority": "P0/P2/P3",
  "test_data": {{"normal": {{}}, "boundary": {{}}, "abnormal": {{}}}},
  "steps": [
    {{
      "step": "1",
      "description": "步骤1描述",
      "action": "具体的业务操作描述",
      "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
      "input_value": "输入值（仅input类型有值，其他为空字符串）",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_result": "所有步骤预期结果的汇总描述"
}}

## 生成规则
1. **步骤要求**：每个步骤必须是原子操作；action_type必须是枚举值之一；input_value仅input/select填写；expected_result必须是可验证条件
2. **前置条件**：不要描述登录操作或包含账号密码；precondition写为"系统已通过配置自动登录至目标页面"
3. **用例类型**：ui_automation(UI交互)/manual(人工判断)/api_automation(接口验证)/performance(性能)/security(安全)
4. **优先级**：P0(核心功能)/P2(一般验证)/P3(边界异常)
5. **覆盖要求**：必须覆盖需求文档所有功能点；每个测试点至少一个用例；有UI原型图时操作对象须与UI元素对应
6. **格式统一**：step字段为字符串类型；必须包含test_data字段（normal/boundary/abnormal三个空对象）
"""

    client = get_ai_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
            response = client.chat.completions.create(
                model=client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            resp_content = response.choices[0].message.content
            if not resp_content:
                raise AIResponseParseError("AI返回内容为空")
            resp_content = resp_content.strip()
            if resp_content.startswith("```"):
                resp_content = re.sub(r'^```(?:json)?\s*\n?', '', resp_content)
                resp_content = re.sub(r'\n?```\s*$', '', resp_content)
                resp_content = resp_content.strip()
            generated_case = None
            try:
                generated_case = json.loads(resp_content)
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', resp_content)
                if json_match:
                    try:
                        generated_case = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        fixed = fix_common_json_issues(json_match.group(0))
                        if fixed:
                            try:
                                generated_case = json.loads(fixed)
                            except json.JSONDecodeError:
                                pass
            if generated_case and isinstance(generated_case, dict):
                if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
                    generated_case = normalize_new_format(generated_case)
                else:
                    generated_case = normalize_old_format(generated_case)
                logger.info("增强版AI生成测试用例成功")
                return generated_case
            logger.warning(f"AI返回内容无法解析 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise AIResponseParseError("AI返回内容无法解析为有效的测试用例")
        except (AIResponseParseError, AIResponseFormatError):
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            logger.error(f"增强版AI生成测试用例失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise AIServiceError(f"增强版AI生成测试用例失败: {str(e)}")
    raise AIServiceError("增强版AI生成测试用例失败: 超过最大重试次数")


def generate_test_case(test_point: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if context:
        context['test_points'] = [test_point]
        return generate_test_case_enhanced(context)
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
