from typing import Dict, Any, Tuple

from app.services.prompt_builder.comparison_examples import (
    get_comparison_examples,
    get_title_spec_rules,
    get_precondition_spec_rules,
    get_automation_friendly_rules,
)
from app.utils.ai_client_enhanced._enhanced_context import (
    _normalize_test_points,
    _normalize_ui_specs,
    _stringify_ui_description,
)


def _build_priority_rules(has_ui: bool, has_requirement: bool, has_test_point: bool) -> str:
    rules = """## 信息优先级与冲突规则（必须遵守）
1. 信息优先级：当前测试点 > 关联需求文档 > 当前UI元素(ui_spec) > UI流程/navigation_flow > 历史用例摘要
2. UI元素存在性仅依据当前UI解析结果(ui_spec)。不得使用未在当前UI上下文中出现的按钮、输入框、链接或页面元素
3. 需求与UI不一致时，以需求为准，但涉及UI交互的步骤必须标记【待确认UI】
4. ui_spec缺失或解析失败时，不得臆造元素；需要交互时必须标记【待确认UI】
5. 历史用例仅用于避免重复，不代表当前测试点必须覆盖同类场景；不得照搬、改写或合并历史用例步骤
6. 缺少信息时输出【待补充】或【待确认UI】，禁止编造页面、按钮、字段、接口或业务规则

## 硬约束
- 禁止使用需求中未提及的规则或UI中不存在的元素
- 缺失信息必须标记【待补充】或【待确认UI】
- 权重规则仅为可信上下文内的二级提示策略，不能覆盖上述来源优先级"""

    if not has_requirement:
        rules += "\n\n⚠️ **缺少需求文档**：可能导致生成的测试用例偏离实际业务功能。请基于现有信息生成合理的测试用例，但需注意可能无法完全贴合实际需求。UI或历史用例不得升级为业务事实来源。"
    if not has_ui:
        rules += "\n\n⚠️ **缺少UI原型图**：不得编造按钮、输入框、页面区域、弹窗或跳转入口。如测试点必须涉及UI操作，请使用【待确认UI】标记。优先生成基于需求、业务规则、接口或人工验证视角的测试用例。"
    if not has_test_point:
        rules += "\n\n⚠️ **缺少测试点**：请从需求文档的每个功能点自动推断需要生成的测试用例，但不得超出需求文档定义的功能边界。"

    return rules


def _build_generation_prompt(context: Dict[str, Any]) -> Tuple[str, int]:
    """构建线性模式的测试用例生成 Prompt。

    从 context 中提取并归一化需求、测试点、UI 原型、历史用例等信息，
    组装为完整的生成 Prompt。

    Args:
        context: 生成上下文字典

    Returns:
        (prompt, min_case_count) 元组，prompt 为完整提示词，
        min_case_count 为本次生成要求的最少用例数。
    """
    from app.utils.ai_client_prompt import (
        sanitize_input,
        build_ui_specs_description, build_project_env_info
    )
    raw_requirement = (
        context.get('requirement_content')
        or context.get('requirement')
        or context.get('requirement_text')
        or ''
    )
    requirement = sanitize_input(str(raw_requirement))
    test_points = _normalize_test_points(context)
    ui_specs = _normalize_ui_specs(context.get('ui_specs'))
    raw_ui_description = _stringify_ui_description(
        context.get('ui_description') or context.get('ui_descriptions')
    )
    project_config = context.get('project_config')
    if not isinstance(project_config, dict):
        project_config = {}
    extra_requirements = sanitize_input(str(context.get('extra_requirements') or ''), max_length=10000)
    has_requirement = bool(requirement and requirement.strip())
    ui_desc = (
        build_ui_specs_description(ui_specs)
        if ui_specs
        else sanitize_input(raw_ui_description)
    )
    has_ui = bool(ui_specs)
    has_ui_reference = has_ui or bool(ui_desc and ui_desc.strip() and ui_desc.strip() not in ("[]", "{}", ""))
    has_test_point = bool(test_points)
    min_case_count = 3 if (len(test_points) >= 2 if test_points else False) else 1
    priority_rules = _build_priority_rules(has_ui, has_requirement, has_test_point)
    if not has_ui:
        ui_desc = "无UI原型图解析结果"
    env_desc = build_project_env_info(project_config)
    history_cases = context.get('history_cases', [])
    history_cases_text = ""
    if history_cases:
        history_cases_text = "## 项目已有测试用例（覆盖摘要，仅供避重参考）\n\n"
        history_cases_text += "以下为项目已有的测试用例摘要，仅供避免重复生成使用：\n"
        history_cases_text += "- 这些用例已覆盖的场景无需重复生成\n"
        history_cases_text += "- 请仅生成新场景的用例，不要改写或废弃已有用例\n"
        history_cases_text += "- 已有用例的维护由保鲜建议流程单独处理\n\n"
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
    extra_requirements_text = ""
    if extra_requirements:
        extra_requirements_text = f"""## 补充生成要求
{extra_requirements}

---
"""
    prompt = f"""你是一名高级测试工程师，请根据以下信息生成一个高质量的测试用例。

{priority_rules}

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

{extra_requirements_text}

## 输出格式要求
0. {'必须返回测试用例，覆盖正向（case_category=positive）、边界（case_category=boundary）、异常（case_category=exception）三种测试类型。如果需求或UI涉及多个功能点或页面，请为每个功能点分别生成用例，总数不少于3条' if min_case_count >= 3 else '必须返回至少1条正向用例（case_category=positive）。仅在条件允许时补充边界（case_category=boundary）或异常（case_category=exception）用例，不要为了凑数而生成低质量用例'}
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
    "change_type": "added"
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
        if case_type == "ui_automation" and not has_ui:
            prompt += (
                "当前项目未提供UI原型图，ui_automation降级为草稿模式。\n"
                "所有用例的 case_type 字段填写 \"manual\"，不得填写 \"ui_automation\"。\n"
                "涉及UI交互的步骤必须标记【待确认UI】，不得编造按钮、输入框等页面元素。\n"
                "优先生成基于需求、业务规则或人工验证视角的测试用例。\n"
            )
            case_type = "manual"
        else:
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

    prompt += f"\n{get_automation_friendly_rules()}\n"
    return prompt, min_case_count
