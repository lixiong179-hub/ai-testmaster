"""线性模式 Prompt 构建 - 测试用例线性生成的 Prompt 逻辑。

提供:
    - _build_linear_prompt: 线性模式 Prompt 构建
"""
import json
from typing import List, Dict, Any, Optional

from app.services.prompt_builder.ui_spec_formatter import format_ui_specs_list
from app.services.prompt_builder.comparison_examples import get_comparison_examples


def _build_history_cases_section(history_cases: Optional[List[Dict[str, Any]]]) -> str:
    """构建历史参考用例章节，非空时返回章节文本，空时返回空字符串。

    业务原因：_scoring_mixin 填充的历史用例需注入 Prompt 供 AI 参考风格与结构，
    避免直接复制。取 top 3（按 trust_level 降序），总长度上限 300 字符。
    """
    if not history_cases:
        return ""

    trust_order = {"high": 0, "medium": 1, "low": 2}
    sorted_cases = sorted(
        history_cases,
        key=lambda c: trust_order.get(str(c.get("trust_level", "low")).lower(), 3)
    )[:3]

    lines = [
        "## 历史参考用例",
        "以下为同项目历史高质量用例，供参考风格与结构（勿直接复制）：",
    ]
    for idx, case in enumerate(sorted_cases, 1):
        trust = case.get("trust_level", "medium")
        title = case.get("title", "")
        # _summarize_history_case 产出不含 steps 字段，统一用 summary
        step_summary = case.get("summary", "")
        lines.append(f"{idx}. [信任度:{trust}] {title}")
        if step_summary:
            lines.append(f"   - {step_summary}")

    section = "\n".join(lines)
    if len(section) > 300:
        section = section[:297] + "..."
    return section


def _extract_ui_supplement_info(ui_description: str) -> str:
    """从 ui_description 提取 navigation_flow/match_confidence 补充信息。

    业务原因：ui_specs 存在时 ui_description 仍可能含导航流程等关键信息，
    完全忽略会导致 AI 缺失上下文。仅提取结构化字段，避免重复注入纯描述文本。

    兼容两种格式：
        1. JSON 字符串：按 key 提取 navigation_flow/match_confidence（含中文键）。
        2. 纯文本：按关键词提取相关行。

    Args:
        ui_description: UI 描述文本，可能是 JSON 字符串或纯文本。

    Returns:
        补充信息章节文本；无相关信息时返回空字符串（不产生空章节）。
    """
    if not ui_description or not ui_description.strip():
        return ""

    supplement_parts: List[str] = []
    stripped = ui_description.strip()

    # 优先尝试 JSON 解析（结构化场景）
    is_json = False
    try:
        data = json.loads(stripped)
        is_json = True
        if isinstance(data, dict):
            nav_flow = data.get("navigation_flow") or data.get("导航流程")
            if nav_flow:
                supplement_parts.append(f"导航流程: {nav_flow}")
            match_conf = data.get("match_confidence") or data.get("匹配置信度")
            if match_conf:
                supplement_parts.append(f"匹配置信度: {match_conf}")
    except json.JSONDecodeError:
        pass

    # 纯文本场景：按关键词提取相关行
    if not is_json:
        keywords = ("navigation_flow", "导航流程", "match_confidence", "匹配置信度")
        for line in ui_description.split("\n"):
            line_stripped = line.strip()
            if line_stripped and any(kw in line for kw in keywords):
                supplement_parts.append(line_stripped)

    if not supplement_parts:
        return ""

    return "## UI原型图补充信息\n" + "\n".join(supplement_parts)


def _build_linear_prompt(
    requirement_content: str,
    ui_description: str,
    module: str,
    function: str,
    point: str,
    priority: int,
    ui_specs: Optional[List[Dict[str, Any]]] = None,
    case_type: Optional[str] = None,
    min_case_count: int = 3,
    history_cases: Optional[List[Dict[str, Any]]] = None,
    project_id: Optional[int] = None,
    db: Any = None,
    execution_feedback: Optional[str] = None,
) -> str:
    """构建线性模式的 Prompt。

    Args:
        requirement_content: 需求文档内容。
        ui_description: UI 描述文本。
        module: 模块名称。
        function: 功能名称（AI中间产物，不存库）。
        point: 测试点描述。
        priority: 优先级。
        ui_specs: UI 规格列表。
        case_type: 用例类型约束。
        min_case_count: 最少用例数。
        history_cases: 历史用例列表。
        project_id: 项目ID，用于加载领域 Few-shot 示例。
        db: 数据库会话，用于加载领域示例。
        execution_feedback: 历史执行失败归因文本，注入 Prompt 指导避坑。

    Returns:
        完整的 Prompt 字符串。
    """
    ui_spec_text = format_ui_specs_list(ui_specs or [])

    if ui_spec_text:
        ui_section = f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_spec_text}"
        # Task 10: ui_specs 存在时仍从 ui_description 提取补充信息，避免完全忽略
        ui_supplement = _extract_ui_supplement_info(ui_description)
        if ui_supplement:
            ui_section = f"{ui_section}\n\n{ui_supplement}"
    elif ui_description and ui_description.strip():
        ui_section = f"## UI原型图描述：\n{ui_description}"
    else:
        ui_section = "## UI原型图描述：[无UI原型图信息]"

    test_point_json = json.dumps({
        "module": module, "function": function, "point": point, "priority": priority
    }, ensure_ascii=False)

    case_type_section = ""
    if case_type:
        type_guidance = {
            "ui_automation": "步骤必须包含UI元素交互，预期结果必须可自动化断言。",
            "manual": "允许包含人工判断步骤，但仍需写清可执行操作和明确预期。",
            "api_automation": "用例必须聚焦接口请求、响应字段、状态码和数据一致性断言，不要依赖UI元素。",
            "performance": "用例必须包含响应时间、并发、吞吐量或资源占用等可量化指标。",
            "security": "用例必须聚焦权限、注入、敏感数据、越权或安全策略验证。",
        }.get(case_type, "")
        case_type_section = f"""
## 用例类型约束：
所有用例的 case_type 字段必须统一为 "{case_type}"，不允许生成其他类型的用例。
{type_guidance}
"""

    history_section = _build_history_cases_section(history_cases)

    # Task 7: 加载项目领域 Few-shot 示例
    domain_section = ""
    if project_id is not None and db is not None:
        from app.services.prompt_builder.domain_examples import get_domain_examples
        # get_domain_examples 返回 None 时保留通用示例（domain_section 保持空串）
        domain_section = get_domain_examples(db, project_id) or ""

    # Task 12: 注入历史执行失败归因
    execution_feedback_section = ""
    if execution_feedback:
        execution_feedback_section = f"## 历史执行失败归因（请避免同类问题）：\n{execution_feedback}"

    return f"""你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下信息生成详细的、可执行的测试用例。

## 测试点信息（JSON格式）：
{test_point_json}

## 需求文档内容：
{requirement_content if requirement_content else '[无需求文档内容]'}

{ui_section}

{case_type_section}

{history_section}

{domain_section}

{execution_feedback_section}

## 上下文优先级与冲突规则（必须遵守）：
1. 信息优先级：当前测试点 > 关联需求文档 > 当前UI元素(ui_spec) > UI流程/navigation_flow > 历史用例摘要。
2. UI元素存在性仅依据当前UI解析结果(ui_spec)。不得使用未在当前UI上下文中出现的按钮、输入框、链接或页面元素。
3. 需求与UI不一致时，以需求为准，但涉及UI交互的步骤必须标记【待确认UI】。
4. ui_spec缺失或解析失败时，不得臆造元素；需要交互时必须标记【待确认UI】。
5. 历史用例仅用于避免重复，不代表当前测试点必须覆盖同类场景；不得照搬、改写或合并历史用例步骤。
6. 页面导航关系与需求文档矛盾时，以需求文档为准。
7. 缺少信息时输出【待补充】或【待确认UI】，禁止编造页面、按钮、字段、接口或业务规则。

## 覆盖要求（核心）：
你必须根据测试点的复杂度自行判断生成用例数量，最少{min_case_count}条，且必须覆盖以下测试类型：
- 正向用例（Happy Path）：主流程正常操作，至少1条
- 边界值用例：输入/状态/数据的边界条件，至少1条
- 异常用例：错误输入、权限缺失、网络异常、容错等，至少1条
- 安全/性能用例（如涉及）：权限越权、并发、大数据量等，至少1条
如果测试点涉及安全或性能场景，也应补充对应用例。
每条用例必须覆盖不同的测试场景，禁止生成内容高度相似的重复用例。

## 输出要求：
1. 只输出JSON数组格式内容，不要添加任何其他文字
2. 数组中每个对象必须包含以下字段：
   - title: 用例标题（必须具体明确，格式：场景/条件+操作+验证重点，如"无网络时提交批改显示网络错误提示"，禁止"功能验证""界面测试"等模糊词，长度15-40字）
   - module: 模块名称
   - precondition: 前置条件（必须包含"账号已登录"和网络环境（Web端写"浏览器网络正常"，App端写"设备网络正常"），有权限场景补充权限状态；禁止仅写"账号已登录"或"APP运行正常"；前置条件只约束环境与权限，禁止依赖特定业务数据（如"列表有数据""数据较多"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在；前置条件不能包含操作步骤或页面导航状态（如"已进入详情页""在列表页面"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行；前置条件禁止包含Mock、cy.intercept、ADB、devtools、token、cookie、session、localStorage等技术实现细节，只描述业务状态和环境权限；未登录状态用"用户未登录"描述，禁止写"清除token"或"清除cookie"）
   - test_data: 测试数据对象（可选，如有特定测试数据如输入值、文件类型等请填写，无则可省略该字段）
   - steps: 测试步骤数组，每个步骤必须包含：
     * step: 步骤序号（如"1"、"2"、"3"等）
     * description: 步骤描述（必须严谨可复现，禁止口语化如"连续拍摄多张照片"）
     * action: 具体操作（必须是完整的业务操作描述如"点击提交按钮""输入用户名admin"，禁止只写操作类型关键词如"click""input"）
     * action_type: 操作类型，严格按以下规则判定：click=所有点击/勾选/选择/切换/按下/长按操作（只要手指/鼠标点击了屏幕元素就是click）；input=所有键盘输入/填写/键入操作；navigate=仅用于页面自动跳转/等待加载完成/静置等待（不涉及用户主动点击的操作）；scroll=页面滚动/滑动操作；verify=验证断言步骤（查看/检查/确认/核对页面元素状态但不执行任何操作）；select=下拉选择操作；判定口诀：action描述含"点击"必为click，含"输入/填写"必为input，含"查看/检查/验证/确认"且不点击任何元素时为verify，仅"等待/静置"时为navigate
     * input_value: 输入值（click类为空字符串，input类为具体输入值）
     * target_element: 目标元素描述（如"用户名输入框""提交按钮""列表区域"）
     * expected_result: 该步骤对应的预期结果（必须按三段式格式书写"【元素状态】+【具体文案/数值】+【交互结果】"，如"按钮由置灰变为可点击（从disabled态变为enabled态），点击后跳转至首页（URL包含/home）"；禁止"提交成功""正常显示""功能正常""交互跳转正确""无崩溃白屏""UI元素完整"等模糊描述）
     * param: 操作参数（可选，click类为空字符串，input类为输入值）
   - expected_result: 总体预期结果（必须包含交互校验点如弹窗文案、按钮跳转、元素状态变化，禁止只写大致结果）
   - case_type: 用例类型（ui_automation/manual/api_automation/performance/security）
   - priority: 优先级（1高/2中/3低）
   - case_category: 用例测试类型（positive=正向场景, boundary=边界场景, exception=异常场景）
   - 原子性原则：一条用例只验证一个测试场景，禁止将主流程与分支/旁路逻辑混合在一条用例中
   - 步骤确定性原则：每个步骤的操作必须唯一确定，禁止使用"或""或者"等不确定措辞
   - 步骤原子性原则：每个步骤只能包含一种action_type；例如"点击修改、输入内容、点击确认"必须拆成click、input、click三步
   - 步骤独立性原则：禁止写"参见正向用例步骤""重复上一步""同上"等引用式步骤，每一步都必须写出完整可执行动作
   - 自动化可执行原则：case_type为ui_automation时，禁止步骤中出现"手动判断""人工确认""目测"等需要人工介入的描述
   - 自动化友好：步骤和预期必须支持自动化断言，预期需有可量化判定标准（如"无白屏""按钮置灰"），禁止"页面正常""功能正常"等无法断言的描述；步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中；弱网、异常条件等自动化无法实现的场景标注case_type为manual
   - 最少步骤原则：每条用例至少2步（导航到目标页面+核心操作/验证），前置条件中的状态必须通过步骤到达，禁止生成仅1步的用例
   - 最多步骤原则：每条用例最多8步，超过8步说明用例混合了多个测试场景，必须拆分为多条独立用例

{get_comparison_examples(compact=True)}

## 用例分类标签说明：
- ui_automation: UI自动化测试用例 - 可通过Selenium/Appium等工具自动化执行
- manual: 手工测试用例 - 需要人工执行，无法自动化
- api_automation: 接口自动化测试用例 - 通过HTTP请求验证后端逻辑

根据测试点的性质和界面复杂度判断：
- 涉及UI交互（表单、按钮、输入）→ ui_automation（如果元素可定位）或 manual（如果元素难以定位）
- 纯后端逻辑验证（API调用、数据校验）→ api_automation
- 复杂用户体验测试 → manual

## 输出JSON格式（数组，最少{min_case_count}条）：
[
  {{
    "title": "正向场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "点击目标元素", "action_type": "click", "input_value": "", "target_element": "目标元素", "param": "", "expected_result": "步骤1的预期结果"}},
      {{"step": "2", "description": "步骤2描述", "action": "输入测试数据", "action_type": "input", "input_value": "输入值", "target_element": "输入框元素", "param": "", "expected_result": "步骤2的预期结果"}}
    ],
    "expected_result": "总体预期结果",
    "case_type": "ui_automation",
    "case_category": "positive",
    "priority": 优先级
  }},
  {{
    "title": "边界场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "test_data": {{"input": "边界值示例", "expected": "对应结果"}},
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "点击目标元素", "action_type": "click", "input_value": "", "target_element": "目标元素", "param": "", "expected_result": "步骤1的预期结果"}},
      {{"step": "2", "description": "步骤2描述", "action": "输入边界值", "action_type": "input", "input_value": "边界值", "target_element": "输入框元素", "param": "", "expected_result": "步骤2的预期结果"}}
    ],
    "expected_result": "边界验证预期结果",
    "case_type": "ui_automation",
    "case_category": "boundary",
    "priority": 优先级
  }},
  {{
    "title": "异常场景+操作+验证重点",
    "module": "模块名称",
    "precondition": "前置条件",
    "steps": [
      {{"step": "1", "description": "步骤1描述", "action": "点击目标元素", "action_type": "click", "input_value": "", "target_element": "目标元素", "param": "", "expected_result": "步骤1的预期结果"}},
      {{"step": "2", "description": "步骤2描述", "action": "查看错误提示", "action_type": "verify", "input_value": "", "target_element": "提示元素", "param": "", "expected_result": "步骤2的预期结果"}}
    ],
    "expected_result": "异常处理预期结果",
    "case_type": "manual",
    "case_category": "exception",
    "priority": 优先级
  }}
]"""
