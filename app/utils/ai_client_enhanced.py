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
    clean_json_string,
    infer_action_type,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)
from app.services.prompt_builder.comparison_examples import (
    get_comparison_examples,
    get_title_spec_rules,
    get_precondition_spec_rules,
    get_automation_friendly_rules,
)
from app.services.test_case_generation.quality_validator import (
    validate_cases_quality,
    compute_quality_score,
    QUALITY_MIN_SCORE,
)

AI_GENERATE_MAX_TOKENS = 16384


def _repair_truncated_json(json_str: str) -> Optional[str]:
    if not json_str or len(json_str) < 10:
        return None
    repaired = json_str.rstrip()
    if repaired.endswith(']') or repaired.endswith('}'):
        return None
    in_string = False
    escape_next = False
    for ch in repaired:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
    if in_string:
        repaired += '"'
    last_brace = repaired.rfind('}')
    last_bracket = repaired.rfind(']')
    last_struct = max(last_brace, last_bracket)
    if last_struct > 0:
        repaired = repaired[:last_struct + 1]
    repaired = re.sub(r',\s*$', '', repaired)
    open_brackets = 0
    open_braces = 0
    in_string = False
    escape_next = False
    for ch in repaired:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1
        elif ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
    while open_braces > 0:
        repaired += '}'
        open_braces -= 1
    while open_brackets > 0:
        repaired += ']'
        open_brackets -= 1
    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return None


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
0. 必须返回测试用例，至少覆盖正向（case_category=positive）、边界（case_category=boundary）、异常（case_category=exception）三种测试类型，每种类型至少1条用例。如果需求或UI涉及多个功能点或页面，请为每个功能点分别生成用例，总数不少于3条
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

{get_title_spec_rules()}

{get_precondition_spec_rules()}

{get_comparison_examples()}

## 生成规则
1. **步骤要求**：每个步骤必须是原子操作；action_type必须是枚举值之一；input_value仅input/select填写；expected_result必须是可验证条件
2. **用例类型**：ui_automation(UI交互)/manual(人工判断)/api_automation(接口验证)/performance(性能)/security(安全)
3. **优先级**：P0(核心功能)/P2(一般验证)/P3(边界异常)
4. **覆盖要求**：必须覆盖需求文档所有功能点；每个测试点至少一个用例；有UI原型图时操作对象须与UI元素对应
5. **格式统一**：step字段为字符串类型；必须包含test_data字段（normal/boundary/abnormal三个空对象）
"""

        case_type = context.get('case_type')
        if case_type:
            prompt += f"\n## 用例类型约束\n"
            prompt += f"所有用例的 case_type 字段必须统一为 \"{case_type}\"，不允许生成其他类型的用例。\n"
            type_guidance = {
                "ui_automation": "步骤必须包含UI元素交互，action_type使用click/input/scroll等UI操作，预期结果可自动化验证",
                "manual": "允许包含需要人工判断的步骤，预期结果允许主观描述，不要求完全可自动化",
                "api_automation": "用例聚焦接口层面验证，步骤以API请求/响应断言为主，无需UI元素引用",
                "performance": "关注响应时间、并发数、吞吐量等性能指标，预期结果包含数值阈值",
                "security": "关注XSS注入、SQL注入、权限绕过、敏感数据泄露等安全验证点",
            }
            extra = type_guidance.get(case_type, "")
            if extra:
                prompt += f"{extra}\n"

        prompt += f"""
{get_automation_friendly_rules()}
"""

    client = get_ai_client()
    max_retries = 3
    messages = [{"role": "user", "content": prompt}]
    is_graph_mode = bool(graph_prompt)
    min_case_count = 3 if is_graph_mode else 1
    for attempt in range(max_retries):
        try:
            logger.info(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
            response = client.chat.completions.create(
                model=client.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=AI_GENERATE_MAX_TOKENS
            )
            resp_content = response.choices[0].message.content
            if not resp_content:
                raise AIResponseParseError("AI返回内容为空")
            resp_content = resp_content.strip()
            code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', resp_content)
            if code_block_match:
                resp_content = code_block_match.group(1).strip()
            elif resp_content.startswith("```"):
                resp_content = re.sub(r'^```(?:json)?\s*\n?', '', resp_content)
                resp_content = re.sub(r'\n?```\s*$', '', resp_content)
                resp_content = resp_content.strip()
            generated_case = None
            try:
                generated_case = json.loads(resp_content)
            except json.JSONDecodeError:
                json_match = re.search(r'\[[\s\S]*\]\s*$', resp_content)
                if not json_match:
                    json_match = re.search(r'\{[\s\S]*\}', resp_content)
                if json_match:
                    matched_str = json_match.group(0)
                    try:
                        generated_case = json.loads(matched_str)
                    except json.JSONDecodeError:
                        fixed = fix_common_json_issues(matched_str)
                        if fixed:
                            try:
                                generated_case = json.loads(fixed)
                            except json.JSONDecodeError:
                                pass
                        if generated_case is None:
                            cleaned = clean_json_string(matched_str)
                            if cleaned:
                                try:
                                    generated_case = json.loads(cleaned)
                                except json.JSONDecodeError:
                                    pass
                        if generated_case is None:
                            repaired = _repair_truncated_json(matched_str)
                            if repaired:
                                try:
                                    generated_case = json.loads(repaired)
                                except json.JSONDecodeError:
                                    pass
            if generated_case is not None:
                normalized_cases: list = []
                if isinstance(generated_case, list):
                    for case_item in generated_case:
                        if isinstance(case_item, dict):
                            if 'expected_results' in case_item and isinstance(case_item.get('expected_results'), list):
                                normalized_cases.append(normalize_new_format(case_item))
                            else:
                                normalized_cases.append(normalize_old_format(case_item))
                elif isinstance(generated_case, dict):
                    if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
                        normalized_cases.append(normalize_new_format(generated_case))
                    else:
                        normalized_cases.append(normalize_old_format(generated_case))
                if not normalized_cases:
                    logger.warning(f"AI返回内容格式化后为空 (尝试 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise AIResponseParseError("AI返回内容格式化后为空")
                passed, issues = validate_cases_quality(normalized_cases, min_count=min_case_count)
                quality_score = compute_quality_score(normalized_cases)
                if passed:
                    logger.info(
                        f"增强版AI生成测试用例成功，共{len(normalized_cases)}条，质量分{quality_score:.0f}"
                    )
                    return normalized_cases
                if quality_score >= QUALITY_MIN_SCORE:
                    logger.warning(
                        f"用例质量分{quality_score:.0f}≥阈值{QUALITY_MIN_SCORE}，"
                        f"存在次要问题: {issues}"
                    )
                    return normalized_cases
                if attempt < max_retries - 1:
                    feedback = (
                        "上一次生成的用例存在以下质量问题，请逐一修正后重新生成：\n"
                        + "\n".join(f"- {issue}" for issue in issues)
                    )
                    messages.append({"role": "assistant", "content": resp_content[:3000]})
                    messages.append({"role": "user", "content": feedback})
                    logger.warning(
                        f"用例质量分{quality_score:.0f}<阈值{QUALITY_MIN_SCORE}，"
                        f"触发质量反馈重试 (尝试 {attempt + 1}/{max_retries})，"
                        f"问题数: {len(issues)}"
                    )
                    time.sleep(2)
                    continue
                logger.error(
                    f"用例质量分{quality_score:.0f}<阈值{QUALITY_MIN_SCORE}，"
                    f"已达最大重试次数，降级返回，问题数: {len(issues)}"
                )
                return normalized_cases
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
