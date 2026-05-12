import json
import re
import time
from typing import Dict, Any, Optional, List
from loguru import logger

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
    get_ai_client,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    infer_action_type,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)
from app.services.prompt_builder.comparison_examples import get_comparison_examples

AI_GENERATE_MAX_TOKENS = 8192


def generate_test_case_enhanced(context: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        history_cases = context.get('history_cases', [])
        history_cases_text = ""
        if history_cases:
            history_cases_text = "## 项目已有测试用例（用例评审）\n\n"
            history_cases_text += "以下为项目已有的测试用例，请逐条对照新需求/UI进行评审：\n"
            history_cases_text += "- 查漏：新场景未被任何旧用例覆盖 → 生成新用例（change_type=added）\n"
            history_cases_text += "- 补缺：旧用例的步骤/预期与新代码或UI不一致 → 输出修正后的用例（change_type=modified，parent_case_id=原用例ID）\n"
            history_cases_text += "- 去冗：旧用例对应的场景已不存在 → 标注建议废弃（change_type=deprecated，parent_case_id=原用例ID）\n"
            history_cases_text += "- 保留：旧用例仍完全符合当前场景 → 无需重复生成\n\n"
            for i, case in enumerate(history_cases, 1):
                desc = case.get("summary", "") or case.get("expected_result", "") or "无摘要"
                history_cases_text += f"  {i}. [{case.get('module', '')}] {case.get('title', '')} (ID:{case.get('id', '')}) — {desc}\n"
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

{history_cases_text}

---

## 输出格式要求
0. 必须返回3条测试用例，分别覆盖正向（case_category=positive）、边界（case_category=boundary）、异常（case_category=exception）三种测试类型
请严格按照以下JSON数组格式输出（不要添加markdown代码块标记）：
[
  {{
    "title": "正向场景+操作+验证重点",
    "module": "所属模块",
    "precondition": "系统已通过配置自动登录至目标页面",
    "case_type": "ui_automation/manual/api_automation/performance/security",
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
    "expected_result": "所有步骤预期结果的汇总描述",
    "case_category": "positive",
    "change_type": "added/modified/deprecated（无参考用例时为added）",
    "parent_case_id": "原用例ID（仅modified/deprecated时填写，added时为null）"
  }},
  {{
    "title": "边界场景+操作+验证重点",
    "module": "所属模块",
    "precondition": "系统已通过配置自动登录至目标页面",
    "case_type": "ui_automation/manual/api_automation/performance/security",
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
    "expected_result": "所有步骤预期结果的汇总描述",
    "case_category": "boundary",
    "change_type": "added/modified/deprecated（无参考用例时为added）",
    "parent_case_id": "原用例ID（仅modified/deprecated时填写，added时为null）"
  }},
  {{
    "title": "异常场景+操作+验证重点",
    "module": "所属模块",
    "precondition": "系统已通过配置自动登录至目标页面",
    "case_type": "ui_automation/manual/api_automation/performance/security",
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
    "expected_result": "所有步骤预期结果的汇总描述",
    "case_category": "exception",
    "change_type": "added/modified/deprecated（无参考用例时为added）",
    "parent_case_id": "原用例ID（仅modified/deprecated时填写，added时为null）"
  }}
]

## 标题规范
- 格式：「场景/条件」+「操作」+「验证重点」，如"未选单词时纸张听写按钮置灰不可点击"
- 看到标题即知用例目的，禁止使用"功能验证""界面测试""XX测试"等模糊词
- 好标题："无网络时提交批改显示网络错误提示""编辑状态下未选中生词删除按钮置灰""输入有效邮箱和密码注册成功"
- 坏标题："功能验证""界面测试""听写功能测试""Video Test Case"
- 长度15-40字

## 前置条件规范
- 必须包含"账号已登录"和"设备网络正常"，有权限相关场景必须补充权限状态（如"相机权限已开启"）
- 禁止仅写"账号已登录"或"APP运行正常"等不完整前置

{get_comparison_examples()}

## 生成规则
1. **步骤要求**：每个步骤必须是原子操作；action_type必须是枚举值之一；input_value仅input/select填写；expected_result必须是可验证条件
2. **用例类型**：ui_automation(UI交互)/manual(人工判断)/api_automation(接口验证)/performance(性能)/security(安全)
3. **优先级**：P0(核心功能)/P2(一般验证)/P3(边界异常)
4. **覆盖要求**：必须覆盖需求文档所有功能点；每个测试点至少一个用例；有UI原型图时操作对象须与UI元素对应
5. **格式统一**：step字段为字符串类型；必须包含test_data字段（normal/boundary/abnormal三个空对象）

前置条件规范：
- 必须包含"账号已登录"和网络环境（Web端写"浏览器网络正常"，App端写"设备网络正常"），有权限相关场景必须补充权限状态（如"相机权限已开启"）
- 禁止仅写"账号已登录"或"APP运行正常"等不完整前置
- 前置条件只约束环境与权限，禁止依赖特定业务数据（如"列表有数据""数据较多"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在
- 前置条件不能包含操作步骤或页面导航状态（如"已进入详情页""在列表页面"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行

自动化友好规范：
- 步骤和预期必须支持自动化断言，预期结果需有可量化判定标准（如"无白屏""无接口报错""按钮置灰"）
- 禁止"页面正常""功能正常""没问题"等无法断言的模糊描述
- 步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中
- 弱网、异常条件等自动化无法实现的场景标注case_type为manual
"""

    client = get_ai_client()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
            response = client.chat.completions.create(
                model=client.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=AI_GENERATE_MAX_TOKENS
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
                json_match = re.search(r'\[[\s\S]*\]', resp_content)
                if not json_match:
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
            if generated_case is not None:
                if isinstance(generated_case, list):
                    normalized_cases = []
                    for case_item in generated_case:
                        if isinstance(case_item, dict):
                            if 'expected_results' in case_item and isinstance(case_item.get('expected_results'), list):
                                normalized_cases.append(normalize_new_format(case_item))
                            else:
                                normalized_cases.append(normalize_old_format(case_item))
                    if normalized_cases:
                        logger.info(f"增强版AI生成测试用例成功，共{len(normalized_cases)}条")
                        return normalized_cases
                elif isinstance(generated_case, dict):
                    if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
                        normalized_case = normalize_new_format(generated_case)
                    else:
                        normalized_case = normalize_old_format(generated_case)
                    logger.info("增强版AI生成测试用例成功，共1条")
                    return [normalized_case]
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


def generate_test_case(test_point: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """根据测试点生成测试用例。

    兼容str类型输入：当test_point为字符串时自动构造默认测试点字典，
    并在提供context时委托给增强版生成流程。

    Args:
        test_point: 测试点字典或纯文本描述
        context: AI生成上下文，提供时使用增强版生成

    Returns:
        生成的测试用例字典
    """
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
