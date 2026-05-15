"""测试用例生成 Prompt 构建 - 流程图模式。

提供:
    - _build_graph_prompt: 流程图模式 Prompt 构建
"""
from typing import List, Dict, Any, Optional

from loguru import logger

from app.services.prompt_builder.helpers import (
    _safe_int,
    _infer_condition,
    _render_flow_meta_hint,
    _render_edge_hint,
    _group_edges_by_source,
)
from app.services.prompt_builder.flow_aware_history import (
    _append_flow_aware_history_cases,
)
from app.services.prompt_builder.comparison_examples import (
    get_comparison_examples,
    get_title_spec_rules,
    get_precondition_spec_rules,
    get_automation_friendly_rules,
)


def _build_graph_prompt(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    module_info: Optional[Dict[str, Any]] = None,
    requirement_content: str = "",
    test_point_json: str = "",
    ui_specs_text: str = "",
    include_images: bool = False,
    history_cases: Optional[List[Dict[str, Any]]] = None,
    case_type: Optional[str] = None
) -> str:
    """构建流程图模式的 Prompt。

    Prompt 结构:
        1. 角色设定（资深测试工程师）
        2. 测试点信息（JSON 格式）
        3. 需求文档内容
        4. 模块信息
        5. UI 原型图解析结果
        6. UI 原型图流程结构（主干/分支/异常/旁路）
        7. 项目已有测试用例（流程感知评审，仅 history_cases 存在时）
        8. 生成要求 + 输出格式

    Args:
        nodes: 节点列表，每个节点包含 screen_id/screen_order/flow_type 等。
        edges: 连线列表，每条连线包含 source/target/edge_type/condition 等。
        module_info: 模块基础信息，包含 name 和 description。
        requirement_content: 需求文档内容。
        test_point_json: 测试点 JSON 字符串。
        ui_specs_text: UI 规格格式化文本。
        include_images: 是否在 Prompt 中包含图片 URL。
        history_cases: 历史用例列表，提供时启用流程感知评审模式。
        case_type: 用例类型约束，提供时在生成规则中增加对应约束。

    Returns:
        完整的 Prompt 字符串。
    """
    node_map: Dict[Any, Dict[str, Any]] = {}
    for n in nodes:
        sid = n.get('screen_id')
        if sid in node_map:
            logger.warning(f"重复 screen_id={sid}，后者覆盖前者")
        node_map[sid] = n

    main_nodes = sorted(
        [n for n in nodes if n.get('flow_type') == 'main'],
        key=lambda n: (
            n.get('main_order') or n.get('screen_order', 0),
            n.get('screen_order', 0)
        )
    )

    branch_edges = [e for e in edges if e.get('edge_type') == 'branch']
    exception_edges = [e for e in edges if e.get('edge_type') == 'exception']
    bypass_edges = [e for e in edges if e.get('edge_type') == 'bypass']

    branch_by_source = _group_edges_by_source(branch_edges)
    exception_by_source = _group_edges_by_source(exception_edges)
    bypass_by_source = _group_edges_by_source(bypass_edges)

    parts = []
    parts.append(
        "你是一名资深测试工程师，拥有10年以上的测试经验。"
        "请根据以下多源信息生成详细的、可执行的测试用例。\n"
    )

    if test_point_json:
        parts.append(f"## 测试点信息\n{test_point_json}\n")

    if requirement_content and requirement_content.strip():
        parts.append(f"## 需求文档内容\n{requirement_content}\n")
    else:
        parts.append("## 需求文档内容\n[无需求文档内容]\n")

    if module_info:
        parts.append("## 模块信息")
        parts.append(module_info.get('name', ''))
        parts.append(module_info.get('description', ''))
        parts.append("")

    if ui_specs_text:
        parts.append(f"## UI原型图解析结果（验收标准，优先参考）：\n{ui_specs_text}\n")

    _append_nested_flow(
        parts, main_nodes, node_map,
        branch_by_source, exception_by_source, bypass_by_source, include_images
    )

    if history_cases:
        _append_flow_aware_history_cases(
            parts, history_cases, main_nodes,
            branch_by_source, exception_by_source, bypass_by_source, node_map
        )

    _append_generation_rules(parts, case_type, has_history=bool(history_cases))

    return "\n".join(parts)


def _format_node_elements(elements: Optional[List[Dict[str, Any]]]) -> str:
    """格式化节点的 UI 元素列表为结构化描述。

    保留 type/label/state/interactive/description/semantic 字段，
    为AI生成用例提供充分的元素交互信息。

    Args:
        elements: UI 元素列表。

    Returns:
        分号分隔的元素描述字符串，格式：type:label[state|interactive|desc]。
    """
    if not elements:
        return ""
    parts = []
    for e in elements:
        label = e.get('label', '')
        if not label:
            continue
        etype = e.get('type', '')
        segments = [f"{etype}:{label}"]
        state = e.get('state', '') or 'normal'
        segments.append(f"状态:{state}")
        interactive = e.get('interactive')
        if interactive is True:
            segments.append("可交互")
        elif interactive is False:
            segments.append("不可交互")
        desc = e.get('description') or e.get('semantic', '')
        if desc and isinstance(desc, str) and desc.strip():
            segments.append(desc.strip())
        parts.append('[' + '|'.join(segments) + ']')
    return '; '.join(parts)


def _build_image_ref(node: Dict[str, Any], include_images: bool) -> str:
    """构建节点的图片 URL 引用文本。

    Args:
        node: 节点字典，需包含 image_url 字段。
        include_images: 是否包含图片 URL。

    Returns:
        图片 URL 引用文本，不包含时返回空字符串。
    """
    if include_images and node.get('image_url'):
        return f" [图片URL: {node.get('image_url', '')}]"
    return ""


def _append_nested_flow(
    parts: List[str],
    main_nodes: List[Dict[str, Any]],
    node_map: Dict[Any, Dict[str, Any]],
    branch_by_source: Dict[int, List[Dict[str, Any]]],
    exception_by_source: Dict[int, List[Dict[str, Any]]],
    bypass_by_source: Dict[int, List[Dict[str, Any]]],
    include_images: bool
) -> None:
    """追加嵌套流程描述到 parts 列表：主干步骤下嵌套分支/异常/旁路。

    Args:
        parts: Prompt 片段列表。
        main_nodes: 主干流程节点列表。
        node_map: 节点映射字典。
        branch_by_source: 按源节点分组的分支连线。
        exception_by_source: 按源节点分组的异常连线。
        bypass_by_source: 按源节点分组的旁路连线。
        include_images: 是否包含图片 URL。
    """
    parts.append("## UI原型图流程结构\n")
    parts.append("### 主干流程（按顺序执行，必须完整覆盖）")
    for i, node in enumerate(main_nodes, 1):
        screen_id = node.get('screen_id')
        elements = node.get('ui_spec_elements', []) or []
        element_desc = _format_node_elements(elements)
        image_ref = _build_image_ref(node, include_images)
        summary = (node.get('summary') or '').strip()
        summary_suffix = f" 摘要:{summary}" if summary else ""
        parts.append(
            f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}]"
            f" 元素: {element_desc}{image_ref}{summary_suffix}"
        )

        child_sources = {
            'branch': branch_by_source,
            'exception': exception_by_source,
            'bypass': bypass_by_source,
        }
        child_labels = {'branch': '分支', 'exception': '异常', 'bypass': '旁路'}

        all_children: List[tuple] = []
        for ctype in ('branch', 'exception', 'bypass'):
            for cidx, edge in enumerate(child_sources[ctype].get(screen_id, [])):
                tid = _safe_int(edge.get('target'))
                if tid is not None:
                    all_children.append((ctype, cidx, edge, tid))

        for gidx, (ctype, idx, edge, target_screen_id) in enumerate(all_children):
            is_last = (gidx == len(all_children) - 1)
            branch_sym = '└─' if is_last else '├─'
            indent_prefix = '     ' if is_last else '  │  '

            target_node = node_map.get(target_screen_id, {})
            target_el_desc = _format_node_elements(
                target_node.get('ui_spec_elements', []) or []
            )
            flow_meta = target_node.get('flow_meta') or {}
            img_ref = _build_image_ref(target_node, include_images)
            label = child_labels[ctype]
            condition = _infer_condition(edge, ctype, target_node, node)
            meta_hint = _render_flow_meta_hint(flow_meta, ctype)
            edge_hint = _render_edge_hint(edge)
            target_summary = (target_node.get('summary') or '').strip()
            target_summary_suffix = f" 摘要:{target_summary}" if target_summary else ""

            if ctype == 'branch':
                parts.append(
                    f"  {branch_sym} {label} {chr(ord('A') + idx)}:"
                    f" 触发条件「{condition}」{meta_hint}{edge_hint}"
                )
            elif ctype == 'exception':
                parts.append(
                    f"  {branch_sym} {label} {chr(ord('A') + idx)}:"
                    f" 异常场景「{condition}」{meta_hint}{edge_hint}"
                )
            else:
                parts.append(
                    f"  {branch_sym} {label} {chr(ord('A') + idx)}:"
                    f" {condition}，关闭后继续主流程{meta_hint}{edge_hint}"
                )
            parts.append(
                f"  {indent_prefix}→ [截图 - {target_node.get('screen_name', '')}]"
                f" 元素: {target_el_desc}{img_ref}{target_summary_suffix}"
            )

    parts.append("")


def _append_generation_rules(
    parts: List[str],
    case_type: Optional[str] = None,
    has_history: bool = False,
) -> None:
    """追加生成要求和输出格式到 parts 列表。

    Args:
        parts: Prompt 片段列表。
        case_type: 用例类型，提供时增加对应约束。
        has_history: 是否存在历史用例，为 True 时追加流程感知评审规则。
    """
    parts.append("## 生成要求")
    parts.append("")
    parts.append("### 一、用例结构规范")
    parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
    parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
    parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
    parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
    parts.append(
        "5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；"
        "若未提供，仅根据UI原型图推断业务逻辑"
    )
    parts.append(
        "6. 若提供了测试点，优先覆盖测试点中的测试维度；"
        "若未提供，根据UI元素自动生成测试点"
    )
    parts.append("7. 只输出JSON格式内容，不要添加任何其他文字")
    parts.append(f"8. {get_title_spec_rules(compact=True)}")
    parts.append(f"9. {get_precondition_spec_rules(compact=True)}")
    parts.append("")
    parts.append("### 二、步骤与预期结果规范（核心质量要求）")
    parts.append(
        "10. 操作步骤必须严谨可复现，禁止口语化如\"连续拍摄多张照片\""
    )
    parts.append(
        "11. 预期结果必须按三段式格式书写："
        "\"【元素状态】+【具体文案/数值】+【交互结果】\"；"
        "此规则同时适用于步骤级expected_result和用例级expected_result字段；"
        "三段中至少包含以下一类可客观判定的校验点："
        "元素可见性（如\"弹窗可见\"）、文案内容（如\"提示文案为'网络连接失败'\"）、"
        "状态变化（如\"按钮由置灰变为可点击\"）、数值（如\"正确率显示66.7%\"）、"
        "跳转路径（如\"页面跳转至错词学习页\"）；"
        "禁止\"正常显示\"\"功能正常\"\"交互跳转正确\"\"无崩溃白屏\"\"UI元素完整\"等无法断言的描述"
    )
    parts.append("12. 未区分场景变体时需拆分，如\"无相机权限\"应区分临时拒绝/永久拒绝")
    parts.append(f"14. {get_automation_friendly_rules(compact=True)}")
    parts.append("")
    parts.append("### 三、原子性与确定性规范")
    parts.append(
        "13. 原子性原则：一条用例只验证一个测试场景，"
        "禁止将主流程与分支/旁路逻辑混合在一条用例中；"
        "如需验证\"正确率100%触发话术旁路\"，必须单独生成一条boundary用例，"
        "不得与主流程正向用例合并"
    )
    parts.append(
        "14. 步骤确定性原则：每个步骤的操作必须唯一确定，"
        "禁止使用\"或\"\"或者\"等不确定措辞（如\"点击关闭按钮或弹窗外区域\""
        "\"导航到X页面的URL（或通过接口模拟）\"）；"
        "如存在多种操作路径，应拆分为多条用例分别覆盖"
    )
    parts.append(
        "15. 自动化可执行原则：case_type为ui_automation时，"
        "禁止步骤中出现\"手动判断\"\"人工确认\"\"目测\"等需要人工介入的描述；"
        "所有验证点必须可通过UI元素状态、文案、属性等客观标准判定"
    )
    if has_history:
        parts.append(
            "16. 评审历史用例时，必须对照流程结构逐步骤检查："
            "旧用例的步骤顺序是否与当前流程一致、"
            "是否遗漏新增的分支/异常/旁路、预期结果是否与UI原型匹配"
        )
    parts.append("")
    parts.append("### 四、分类与覆盖规范")
    parts.append(
        "17. 变更类用例必须设置 parent_case_id 为原用例ID、"
        "change_type 为 modified；新增用例 change_type 为 added；"
        "建议废弃的原用例 change_type 为 deprecated"
    )
    parts.append(
        "18. 每条用例必须标注 case_category 字段，"
        "取值范围：positive（正向/主流程）、boundary（边界值）、exception（异常场景），"
        "根据用例的实际测试类型选择对应分类"
    )
    parts.append(
        "19. 最少生成3条用例，必须覆盖："
        "1条主干正向全流程(case_category=positive)、"
        "每个分支节点至少1条(case_category=boundary)、"
        "每个异常节点至少1条(case_category=exception)。禁止只生成1条"
    )
    if case_type:
        parts.append(
            f"20. 所有用例的 case_type 字段必须统一为 \"{case_type}\"，"
            "不允许生成其他类型的用例"
        )
        type_guidance = {
            "ui_automation": (
                "步骤必须包含UI元素交互，action_type使用click/input/scroll等UI操作，"
                "预期结果可自动化验证；"
                "前置条件须声明Mock/桩数据准备方式（如\"通过cy.intercept拦截接口返回指定结果\"），"
                "确保自动化脚本可稳定复现预期行为"
            ),
            "manual": (
                "允许包含需要人工判断的步骤，预期结果允许主观描述，"
                "不要求完全可自动化"
            ),
            "api_automation": (
                "用例聚焦接口层面验证，步骤以API请求/响应断言为主，"
                "无需UI元素引用"
            ),
            "performance": (
                "关注响应时间、并发数、吞吐量等性能指标，"
                "预期结果包含数值阈值"
            ),
            "security": (
                "关注XSS注入、SQL注入、权限绕过、"
                "敏感数据泄露等安全验证点"
            ),
        }
        extra = type_guidance.get(case_type, "")
        if extra:
            parts.append(f"   {extra}")
    parts.append("")
    parts.append(get_comparison_examples())

    parts.append("""
## 输出JSON格式（数组，最少3条）：
注意：steps 中 action 字段必须填写完整的业务操作描述（如"点击提交按钮""在用户名输入框中输入admin"），禁止只写操作类型关键词（如"click""input"）。action_type 字段才填写操作类型枚举值。
重要：expected_result 必须按三段式格式书写"【元素状态】+【具体文案/数值】+【交互结果】"，参考下方示例。步骤数量应根据业务流程自然确定，正向用例通常8-12步，边界和异常用例通常3-6步。

[
  {
    "title": "正向-登录页输入有效账号密码后点击登录验证跳转首页",
    "module": "用户登录",
    "precondition": "浏览器网络正常、测试账号已注册（用户名admin/密码Admin123）",
    "test_data": {"normal": {"用户名": "admin", "密码": "Admin123"}, "boundary": {}, "abnormal": {}},
    "steps": [
      {
        "step": "1",
        "description": "访问登录页面",
        "action": "在浏览器地址栏输入登录页URL并回车",
        "action_type": "navigate",
        "input_value": "/login",
        "target_element": "浏览器地址栏",
        "expected_result": "登录页面加载完成（URL包含/login），用户名输入框和密码输入框可见，登录按钮可见但置灰不可点击（按钮为disabled态）",
        "param": ""
      },
      {
        "step": "2",
        "description": "输入用户名和密码",
        "action": "在用户名输入框中输入admin，在密码输入框中输入Admin123",
        "action_type": "input",
        "input_value": "admin/Admin123",
        "target_element": "用户名输入框/密码输入框",
        "expected_result": "用户名输入框显示admin，密码输入框显示掩码字符，登录按钮由置灰变为可点击（按钮从disabled态变为enabled态）",
        "param": ""
      },
      {
        "step": "3",
        "description": "点击登录按钮",
        "action": "点击登录按钮",
        "action_type": "click",
        "input_value": "",
        "target_element": "登录按钮",
        "expected_result": "按钮显示loading状态（文案变为'登录中...'），请求成功后跳转至首页（URL包含/home），顶部导航栏显示用户头像和用户名admin",
        "param": ""
      }
    ],
    "expected_result": "登录成功后跳转至首页，顶部导航栏显示用户头像和用户名admin，localStorage中存储有效token",
    "case_type": "ui_automation",
    "case_category": "positive",
    "priority": 1,
    "change_type": "added",
    "parent_case_id": null
  },
  {
    "title": "边界-密码输入错误5次后账号锁定15分钟",
    "module": "用户登录",
    "precondition": "浏览器网络正常、测试账号已注册（用户名locktest/密码Test123）、账号当前未锁定",
    "test_data": {"normal": {}, "boundary": {"错误次数": 5}, "abnormal": {}},
    "steps": [
      {
        "step": "1",
        "description": "连续5次输入错误密码点击登录",
        "action": "在用户名输入框输入locktest，在密码输入框输入WrongPwd，点击登录按钮，重复5次",
        "action_type": "input",
        "input_value": "locktest/WrongPwd",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "前4次登录失败后提示'用户名或密码错误'（红色错误文案可见），第5次登录失败后提示'账号已锁定，请15分钟后重试'",
        "param": ""
      },
      {
        "step": "2",
        "description": "锁定期间尝试登录",
        "action": "在用户名输入框输入locktest，在密码输入框输入Test123（正确密码），点击登录按钮",
        "action_type": "input",
        "input_value": "locktest/Test123",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "登录失败，提示'账号已锁定，请15分钟后重试'（红色错误文案可见），不跳转首页",
        "param": ""
      },
      {
        "step": "3",
        "description": "锁定到期后用正确密码登录",
        "action": "等待15分钟后在用户名输入框输入locktest，在密码输入框输入Test123，点击登录按钮",
        "action_type": "input",
        "input_value": "locktest/Test123",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "登录成功，跳转至首页（URL包含/home），顶部导航栏显示用户名locktest",
        "param": ""
      }
    ],
    "expected_result": "连续5次错误密码后账号锁定15分钟（提示文案为'账号已锁定，请15分钟后重试'），锁定期间即使正确密码也登录失败，锁定到期后用正确密码可成功登录跳转首页",
    "case_type": "ui_automation",
    "case_category": "boundary",
    "priority": 2,
    "change_type": "added",
    "parent_case_id": null
  },
  {
    "title": "异常-登录接口超时验证超时提示和重试功能",
    "module": "用户登录",
    "precondition": "浏览器网络正常、测试账号已注册（用户名admin/密码Admin123）、Mock登录接口延迟30秒返回超时",
    "test_data": {"normal": {}, "boundary": {}, "abnormal": {"接口响应": "超时"}},
    "steps": [
      {
        "step": "1",
        "description": "输入有效账号密码点击登录",
        "action": "在用户名输入框输入admin，在密码输入框输入Admin123，点击登录按钮",
        "action_type": "input",
        "input_value": "admin/Admin123",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "按钮显示loading状态（文案变为'登录中...'），等待超时后弹出提示弹窗，弹窗文案为'请求超时，请检查网络后重试'，包含重试按钮和取消按钮",
        "param": ""
      },
      {
        "step": "2",
        "description": "点击重试按钮",
        "action": "点击弹窗中的重试按钮",
        "action_type": "click",
        "input_value": "",
        "target_element": "重试按钮",
        "expected_result": "弹窗关闭，按钮再次显示loading状态，重新发送登录请求",
        "param": ""
      }
    ],
    "expected_result": "接口超时后弹出超时提示弹窗（标题为'请求超时'，文案为'请检查网络后重试'），重试按钮可重新发起请求，取消按钮可关闭弹窗恢复登录页初始状态（输入框保留已输入内容）",
    "case_type": "ui_automation",
    "case_category": "exception",
    "priority": 1,
    "change_type": "added",
    "parent_case_id": null
  }
]""")
