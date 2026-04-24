"""测试用例AI生成 - Prompt构建与UI规格格式化
"""
import json
from typing import List, Dict, Any, Optional


def build_ui_spec_prompt(screen_name: str, ui_spec: Dict[str, Any]) -> str:
    """将ui_spec格式化为AI可理解的文本描述"""
    parts = [f"【页面：{screen_name}】"]

    if ui_spec.get('purpose'):
        parts.append(f"页面功能：{ui_spec['purpose']}")

    regions = ui_spec.get('regions', {})
    if regions:
        parts.append("页面区域：")
        if isinstance(regions, dict):
            for region_name, region_desc in regions.items():
                if region_desc:
                    parts.append(f"  - {region_name}: {region_desc}")
        elif isinstance(regions, list):
            for region in regions:
                if isinstance(region, dict):
                    name = region.get('name', '')
                    desc = region.get('desc', region.get('description', ''))
                    if name or desc:
                        parts.append(f"  - {name}: {desc}")

    elements = ui_spec.get('elements', [])
    if elements:
        parts.append(f"页面元素（共{len(elements)}个）：")
        for elem in elements[:30]:
            elem_type = elem.get('type', '未知')
            label = elem.get('label', '') or elem.get('semantic', '') or elem.get('name', '')
            state = elem.get('state', 'normal')
            interactive = elem.get('interactive', False)
            desc = elem.get('description', '')
            parts.append(f"  - [{elem_type}] {label} | 状态:{state} | 可交互:{interactive} | {desc}")

    navigation = ui_spec.get('navigation', {})
    if navigation:
        parts.append("导航结构：")
        for nav_key, nav_val in navigation.items():
            if nav_val:
                parts.append(f"  - {nav_key}: {nav_val}")

    layout_checks = ui_spec.get('layout_constraints', [])
    if layout_checks:
        parts.append(f"布局约束（共{len(layout_checks)}项）：")
        for check in layout_checks[:10]:
            desc = check.get('description', '')
            if desc:
                parts.append(f"  - {desc}")

    flows = ui_spec.get('flows', {})
    if flows:
        next_screens = flows.get('expected_next_screens', [])
        if next_screens:
            parts.append(f"预期跳转页面：{', '.join(next_screens)}")

    return "\n".join(parts)


def build_generation_prompt(
    requirement_content: str,
    ui_description: str,
    module: str,
    function: str,
    point: str,
    priority: int,
    ui_specs: Optional[List[Dict[str, Any]]] = None
) -> str:
    """构建AI生成测试用例的提示词"""
    ui_spec_text = ""
    if ui_specs:
        spec_parts = []
        for spec_item in ui_specs:
            screen_name = spec_item.get("screen_name", "未命名页面")
            spec = spec_item.get("ui_spec", {})
            if spec:
                spec_parts.append(build_ui_spec_prompt(screen_name, spec))
        if spec_parts:
            ui_spec_text = "\n\n".join(spec_parts)

    if ui_spec_text:
        ui_section = f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_spec_text}"
    elif ui_description and ui_description.strip():
        ui_section = f"## UI原型图描述：\n{ui_description}"
    else:
        ui_section = "## UI原型图描述：[无UI原型图信息]"

    test_point_json = json.dumps({
        "module": module, "function": function, "point": point, "priority": priority
    }, ensure_ascii=False)

    return f"""你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下信息生成详细的、可执行的测试用例。

## 测试点信息（JSON格式）：
{test_point_json}

## 需求文档内容：
{requirement_content if requirement_content else '[无需求文档内容]'}

{ui_section}

## 输出要求：
1. 只输出JSON格式内容，不要添加任何其他文字
2. JSON必须包含以下字段：
   - title: 用例标题
   - module: 模块名称
   - precondition: 前置条件
   - test_data: 测试数据对象
   - steps: 测试步骤数组，每个步骤必须包含：
     * step: 步骤序号（如"1"、"2"、"3"等）
     * description: 步骤描述
     * action: 具体操作
     * expected_result: 该步骤对应的预期结果
   - expected_result: 总体预期结果
   - case_type: 用例类型（ui_automation/manual/api_automation/performance/security）
   - priority: 优先级（1高/2中/3低）
   - case_category: 用例分类标签（ui_automation=UI自动化测试, manual=手工测试, api_automation=接口自动化测试）

## 用例分类标签说明：
- ui_automation: UI自动化测试用例 - 可通过Selenium/Appium等工具自动化执行
- manual: 手工测试用例 - 需要人工执行，无法自动化
- api_automation: 接口自动化测试用例 - 通过HTTP请求验证后端逻辑

根据测试点的性质和界面复杂度判断：
- 涉及UI交互（表单、按钮、输入）→ ui_automation（如果元素可定位）或 manual（如果元素难以定位）
- 纯后端逻辑验证（API调用、数据校验）→ api_automation
- 复杂用户体验测试 → manual

## 输出JSON格式：
{{
  "title": "用例标题",
  "module": "模块名称",
  "precondition": "前置条件",
  "test_data": {{"normal": {{}}, "boundary": {{}}, "abnormal": {{}}}},
  "steps": [
    {{"step": "1", "description": "步骤1描述", "action": "具体操作", "expected_result": "步骤1的预期结果"}},
    {{"step": "2", "description": "步骤2描述", "action": "具体操作", "expected_result": "步骤2的预期结果"}}
  ],
  "expected_result": "总体预期结果",
  "case_type": "ui_automation",
  "case_category": "ui_automation",
  "priority": 优先级
}}"""
