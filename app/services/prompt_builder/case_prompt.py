"""测试用例生成 Prompt 构建 - 流程图模式。

提供:
    - _build_graph_prompt: 流程图模式 Prompt 构建
"""
from typing import List, Dict, Any, Optional

from app.services.prompt_builder.helpers import _safe_int, _infer_condition, _render_flow_meta_hint, _group_edges_by_source
from app.services.prompt_builder.comparison_examples import get_comparison_examples


def _build_graph_prompt(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    module_info: Optional[Dict[str, Any]] = None,
    requirement_content: str = "",
    test_point_json: str = "",
    ui_specs_text: str = "",
    include_images: bool = False,
    history_cases: Optional[List[Dict[str, Any]]] = None
) -> str:
    """构建流程图模式的 Prompt。

    Prompt 结构:
        1. 角色设定（资深测试工程师）
        2. 测试点信息（JSON 格式）
        3. 需求文档内容
        4. UI 原型图解析结果
        5. UI 原型图流程结构（主干/分支/异常/旁路）
        6. 输出格式要求

    Args:
        nodes: 节点列表，每个节点包含 screen_id/screen_order/flow_type 等。
        edges: 连线列表，每条连线包含 source/target/edge_type/condition 等。
        module_info: 模块基础信息，包含 name 和 description。
        requirement_content: 需求文档内容。
        test_point_json: 测试点 JSON 字符串。
        ui_specs_text: UI 规格格式化文本。
        include_images: 是否在 Prompt 中包含图片 URL。

    Returns:
        完整的 Prompt 字符串。
    """
    node_map = {n.get('screen_id'): n for n in nodes}
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

    # Group non-main edges by source (main step) for nested prompt structure
    branch_by_source = _group_edges_by_source(branch_edges)
    exception_by_source = _group_edges_by_source(exception_edges)
    bypass_by_source = _group_edges_by_source(bypass_edges)

    parts = []
    parts.append("你是一名资深测试工程师，拥有10年以上的测试经验。请根据以下多源信息生成详细的、可执行的测试用例。\n")

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

    if history_cases:
        parts.append("## 项目已有测试用例（用例评审）\n")
        parts.append("以下为项目已有的测试用例，请逐条对照新需求/UI进行评审：")
        parts.append("- 查漏：新场景未被任何旧用例覆盖 → 生成新用例（change_type=added）")
        parts.append("- 补缺：旧用例的步骤/预期与新代码或UI不一致 → 输出修正后的用例（change_type=modified，parent_case_id=原用例ID）")
        parts.append("- 去冗：旧用例对应的场景已不存在 → 标注建议废弃（change_type=deprecated，parent_case_id=原用例ID）")
        parts.append("- 保留：旧用例仍完全符合当前场景 → 无需重复生成\n")

        for i, case in enumerate(history_cases, 1):
            desc = case.get("summary", "") or case.get("expected_result", "") or "无摘要"
            parts.append(
                f"  {i}. [{case.get('module', '')}] {case.get('title', '')} "
                f"(ID:{case.get('id', '')}) — {desc}"
            )
        parts.append("")

    _append_nested_flow(parts, main_nodes, node_map, branch_by_source, exception_by_source, bypass_by_source, include_images)
    _append_generation_rules(parts)

    return "\n".join(parts)


def _format_node_elements(elements: Optional[List[Dict[str, Any]]]) -> str:
    """格式化节点的 UI 元素列表为简短描述。

    Args:
        elements: UI 元素列表。

    Returns:
        逗号分隔的元素描述字符串。
    """
    if not elements:
        return ""
    return ', '.join(
        [f"{e.get('type', '')}:{e.get('label', '')}" for e in elements if e.get('label')]
    )


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
        parts.append(f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}] 元素: {element_desc}{image_ref}")

        # Collect all valid children for this step to determine tree symbols dynamically
        valid_branches = []
        for edge in branch_by_source.get(screen_id, []):
            tid = _safe_int(edge.get('target'))
            if tid is not None:
                valid_branches.append((edge, tid))

        valid_exceptions = []
        for edge in exception_by_source.get(screen_id, []):
            tid = _safe_int(edge.get('target'))
            if tid is not None:
                valid_exceptions.append((edge, tid))

        valid_bypasses = []
        for edge in bypass_by_source.get(screen_id, []):
            tid = _safe_int(edge.get('target'))
            if tid is not None:
                valid_bypasses.append((edge, tid))

        all_children = (
            [('branch', bidx, edge, tid) for bidx, (edge, tid) in enumerate(valid_branches)]
            + [('exception', eidx, edge, tid) for eidx, (edge, tid) in enumerate(valid_exceptions)]
            + [('bypass', pidx, edge, tid) for pidx, (edge, tid) in enumerate(valid_bypasses)]
        )

        for cidx, (ctype, idx, edge, target_screen_id) in enumerate(all_children):
            is_last = (cidx == len(all_children) - 1)
            branch_sym = '└─' if is_last else '├─'
            indent_prefix = '     ' if is_last else '  │  '

            target_node = node_map.get(target_screen_id, {})
            target_el_desc = _format_node_elements(target_node.get('ui_spec_elements', []) or [])
            flow_meta = target_node.get('flow_meta') or {}
            img_ref = _build_image_ref(target_node, include_images)

            if ctype == 'branch':
                trigger_condition = _infer_condition(edge, 'branch', target_node, node)
                meta_hint = _render_flow_meta_hint(flow_meta, 'branch')
                parts.append(
                    f"  {branch_sym} 分支 {chr(ord('A') + idx)}: 触发条件「{trigger_condition}」"
                    f"{meta_hint}"
                )
                parts.append(
                    f"  {indent_prefix}→ [截图 - {target_node.get('screen_name', '')}] 元素: {target_el_desc}{img_ref}"
                )
            elif ctype == 'exception':
                exception_condition = _infer_condition(edge, 'exception', target_node, node)
                meta_hint = _render_flow_meta_hint(flow_meta, 'exception')
                parts.append(
                    f"  {branch_sym} 异常 {chr(ord('A') + idx)}: 异常场景「{exception_condition}」"
                    f"{meta_hint}"
                )
                parts.append(
                    f"  {indent_prefix}→ [截图 - {target_node.get('screen_name', '')}] 元素: {target_el_desc}{img_ref}"
                )
            else:  # bypass
                bypass_condition = _infer_condition(edge, 'bypass', target_node, node)
                meta_hint = _render_flow_meta_hint(flow_meta, 'bypass')
                parts.append(
                    f"  {branch_sym} 旁路 {chr(ord('A') + idx)}: {bypass_condition}，关闭后继续主流程"
                    f"{meta_hint}"
                )
                parts.append(
                    f"  {indent_prefix}→ [截图 - {target_node.get('screen_name', '')}] 元素: {target_el_desc}{img_ref}"
                )

    parts.append("")


def _append_generation_rules(parts: List[str]) -> None:
    """追加生成要求和输出格式到 parts 列表。

    Args:
        parts: Prompt 片段列表。
    """
    parts.append("## 生成要求")
    parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
    parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
    parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
    parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
    parts.append("5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；若未提供，仅根据UI原型图推断业务逻辑")
    parts.append("6. 若提供了测试点，优先覆盖测试点中的测试维度；若未提供，根据UI元素自动生成测试点")
    parts.append("7. 只输出JSON格式内容，不要添加任何其他文字")
    parts.append("8. 标题必须具体明确，格式：「场景/条件」+「操作」+「验证重点」，如\"未选单词时纸张听写按钮置灰不可点击\"，禁止使用\"功能验证\"\"界面测试\"\"XX测试\"等模糊词，长度15-40字")
    parts.append("9. 前置条件必须包含\"账号已登录\"和网络环境（Web端写\"浏览器网络正常\"，App端写\"设备网络正常\"），有权限场景补充权限状态；禁止仅写\"账号已登录\"或\"APP运行正常\"；前置条件只约束环境与权限，禁止依赖特定业务数据（如\"列表有数据\"\"数据较多\"），确保用例任意环境可独立执行；如需特定数据才能测试（如编辑/删除场景），应在步骤中先创建数据，而非在前置中假设数据已存在；前置条件不能包含操作步骤或页面导航状态（如\"已进入详情页\"\"在列表页面\"），导航到达目标页面必须作为步骤体现，确保用例可独立自动化执行")
    parts.append("10. 操作步骤必须严谨可复现，禁止口语化如\"连续拍摄多张照片\"")
    parts.append("11. 预期结果必须有具体判定标准，禁止\"提交成功\"\"正常显示\"等模糊描述；必须包含交互校验点如弹窗文案、按钮跳转")
    parts.append("12. 未区分场景变体时需拆分，如\"无相机权限\"应区分临时拒绝/永久拒绝")
    parts.append("13. 步骤和预期必须支持自动化断言，预期需有可量化判定标准（如\"无白屏\"\"按钮置灰\"），禁止\"页面正常\"\"功能正常\"等无法断言的描述；步骤必须包含从登录后到达目标页面的完整导航操作，禁止将导航隐藏在前置条件中；弱网、异常条件等自动化无法实现的场景标注case_type为manual")
    parts.append("14. 若提供了已有测试用例参考，变更类用例必须设置 parent_case_id 为原用例ID、change_type 为 modified；新增用例 change_type 为 added；建议废弃的原用例 change_type 为 deprecated；无参考用例时 change_type 为 added")
    parts.append("15. 每条用例必须标注 case_category 字段，取值范围：positive（正向/主流程）、boundary（边界值）、exception（异常场景），根据用例的实际测试类型选择对应分类")
    parts.append("")
    parts.append(get_comparison_examples())

    parts.append("""
## 输出JSON格式：
{
  "title": "场景+操作+验证重点",
  "module": "模块名称",
  "precondition": "前置条件",
  "test_data": {"normal": {}, "boundary": {}, "abnormal": {}},
  "steps": [
    {
      "step": "1",
      "description": "在用户名输入框中输入admin",
      "action": "input",
      "action_type": "input",
      "input_value": "admin",
      "target_element": "用户名输入框",
      "expected_result": "输入框显示admin",
      "param": "admin"
    }
  ],
  "expected_result": "总体预期结果",
  "case_type": "ui_automation",
  "case_category": "positive",
  "priority": 2,
  "change_type": "added",
  "parent_case_id": null
}""")

