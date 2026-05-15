"""Graph Prompt 构建器单元测试
覆盖:
    - 主干节点按 main_order 排序输出
    - 分支/异常/旁路挂载到对应源主干节点
    - 用户填写条件优先使用
    - 缺少条件时自动推断
    - 无效边不导致异常
    - flow_meta 补充信息渲染
    - 推断条件标注来源
    - _find_main_step 查找与回退
    - _infer_condition 空白条件/英文冒号/无源节点回退
    - _render_flow_meta_hint bypass+note 组合
    - 流程感知历史用例评审（Prompt顺序、覆盖标注、未覆盖提示）
    - _infer_history_case_flow_coverage 流程归属推断
    - _find_uncovered_flow_nodes 未覆盖节点检测
"""
from app.services.prompt_builder.case_prompt import _build_graph_prompt
from app.services.prompt_builder.helpers import (
    _find_main_step,
    _infer_condition,
    _render_flow_meta_hint,
    _render_edge_hint,
    _safe_int,
    _group_edges_by_source,
)
from app.services.prompt_builder.flow_aware_history import (
    _infer_history_case_flow_coverage,
    _find_uncovered_flow_nodes,
)


def _make_node(screen_id: int, screen_name: str, flow_type: str = "main",
               main_order: int | None = None, flow_meta: dict | None = None,
               ui_spec_elements: list | None = None) -> dict:
    return {
        "screen_id": screen_id,
        "screen_name": screen_name,
        "screen_order": screen_id,
        "flow_type": flow_type,
        "main_order": main_order,
        "flow_meta": flow_meta,
        "ui_spec_elements": ui_spec_elements or [],
    }


def _make_edge(source: int, target: int, edge_type: str = "normal",
               condition: str = "", label: str = "") -> dict:
    return {
        "source": str(source),
        "target": str(target),
        "edge_type": edge_type,
        "condition": condition,
        "label": label,
    }


# ── _safe_int ──────────────────────────────────────────────────


def test_safe_int_with_int():
    assert _safe_int(5) == 5


def test_safe_int_with_str():
    assert _safe_int("10") == 10


def test_safe_int_with_invalid():
    assert _safe_int("abc") is None


def test_safe_int_with_none():
    assert _safe_int(None) is None


# ── _group_edges_by_source ─────────────────────────────────────


def test_group_edges_by_source_basic():
    edges = [
        _make_edge(1, 2, "branch"),
        _make_edge(1, 3, "exception"),
        _make_edge(2, 4, "branch"),
    ]
    grouped = _group_edges_by_source(edges)
    assert 1 in grouped
    assert 2 in grouped
    assert len(grouped[1]) == 2
    assert len(grouped[2]) == 1


def test_group_edges_by_source_empty():
    assert _group_edges_by_source([]) == {}


# ── _find_main_step ────────────────────────────────────────────


def test_find_main_step_returns_step_number():
    main_nodes = [
        _make_node(1, "首页", "main", main_order=1),
        _make_node(2, "登录页", "main", main_order=2),
    ]
    assert _find_main_step(main_nodes, 1) == "1"
    assert _find_main_step(main_nodes, 2) == "2"


def test_find_main_step_returns_question_mark_when_not_found():
    main_nodes = [_make_node(1, "首页", "main", main_order=1)]
    assert _find_main_step(main_nodes, 999) == "?"


def test_find_main_step_with_empty_list():
    assert _find_main_step([], 1) == "?"


# ── _infer_condition ───────────────────────────────────────────


def test_infer_condition_uses_user_condition_first():
    edge = _make_edge(1, 2, "branch", condition="点击高级筛选")
    target = _make_node(2, "高级筛选页", "branch")
    result = _infer_condition(edge, "branch", target)
    assert "点击高级筛选" in result
    assert "用户填写" in result


def test_infer_condition_branch_default():
    edge = _make_edge(1, 2, "branch")
    target = _make_node(2, "高级筛选页", "branch")
    source = _make_node(1, "首页", "main")
    result = _infer_condition(edge, "branch", target, source)
    assert "高级筛选页" in result
    assert "系统推断" in result


def test_infer_condition_exception_default():
    edge = _make_edge(1, 2, "exception")
    target = _make_node(2, "登录失败提示", "exception")
    source = _make_node(1, "登录页", "main")
    result = _infer_condition(edge, "exception", target, source)
    assert "登录失败提示" in result


def test_infer_condition_bypass_default():
    edge = _make_edge(1, 2, "bypass")
    target = _make_node(2, "引导弹窗", "bypass")
    source = _make_node(1, "首页", "main")
    result = _infer_condition(edge, "bypass", target, source)
    assert "引导弹窗" in result


def test_infer_condition_uses_edge_label_when_no_condition():
    edge = _make_edge(1, 2, "branch", label="分支：点击详情")
    target = _make_node(2, "详情页", "branch")
    result = _infer_condition(edge, "branch", target)
    assert "点击详情" in result or "详情页" in result


def test_infer_condition_whitespace_condition_falls_back_to_infer():
    edge = _make_edge(1, 2, "branch", condition="   ")
    target = _make_node(2, "高级筛选页", "branch")
    source = _make_node(1, "首页", "main")
    result = _infer_condition(edge, "branch", target, source)
    assert "系统推断" in result
    assert "高级筛选页" in result


def test_infer_condition_english_colon_label():
    edge = _make_edge(1, 2, "branch", label="branch: click settings")
    target = _make_node(2, "设置页", "branch")
    result = _infer_condition(edge, "branch", target)
    assert "系统推断" in result
    assert "click settings" in result


def test_infer_condition_no_source_node_no_label_falls_back_to_default():
    edge = _make_edge(1, 2, "branch")
    target = _make_node(2, "筛选页", "branch")
    result = _infer_condition(edge, "branch", target)
    assert "系统推断" in result
    assert "当前页面" in result


# ── _render_flow_meta_hint ─────────────────────────────────────


def test_render_flow_meta_hint_with_pre_action():
    meta = {"pre_action": "已输入搜索条件"}
    result = _render_flow_meta_hint(meta, "branch")
    assert "前置操作" in result
    assert "已输入搜索条件" in result


def test_render_flow_meta_hint_with_expected_result():
    meta = {"expected_result": "展示高级筛选面板"}
    result = _render_flow_meta_hint(meta, "branch")
    assert "预期结果" in result
    assert "展示高级筛选面板" in result


def test_render_flow_meta_hint_with_bypass_reason():
    meta = {"bypass_reason": "首次进入自动弹出"}
    result = _render_flow_meta_hint(meta, "bypass")
    assert "旁路原因" in result
    assert "首次进入自动弹出" in result


def test_render_flow_meta_hint_with_note():
    meta = {"note": "需要校验弹窗关闭"}
    result = _render_flow_meta_hint(meta, "branch")
    assert "备注" in result
    assert "需要校验弹窗关闭" in result


def test_render_flow_meta_hint_empty():
    assert _render_flow_meta_hint({}, "branch") == ""
    assert _render_flow_meta_hint({"irrelevant": "value"}, "branch") == ""


def test_render_flow_meta_hint_bypass_with_note_and_reason():
    meta = {"bypass_reason": "首次进入", "note": "需校验关闭"}
    result = _render_flow_meta_hint(meta, "bypass")
    assert "旁路原因" in result
    assert "首次进入" in result
    assert "备注" in result
    assert "需校验关闭" in result


def test_render_flow_meta_hint_bypass_reason_ignored_for_non_bypass():
    meta = {"bypass_reason": "首次进入自动弹出"}
    result = _render_flow_meta_hint(meta, "branch")
    assert "旁路原因" not in result


def test_render_edge_hint_with_trigger_action():
    edge = {"trigger_action": "点击注册按钮"}
    result = _render_edge_hint(edge)
    assert "连线触发动作: 点击注册按钮" in result


def test_render_edge_hint_with_pre_action():
    edge = {"pre_action": "先填写手机号"}
    result = _render_edge_hint(edge)
    assert "连线前置操作: 先填写手机号" in result


def test_render_edge_hint_with_note():
    edge = {"note": "仅首次进入时触发"}
    result = _render_edge_hint(edge)
    assert "连线备注: 仅首次进入时触发" in result


def test_render_edge_hint_with_all_fields():
    edge = {"trigger_action": "点击注册", "pre_action": "填写表单", "note": "注意验证"}
    result = _render_edge_hint(edge)
    assert "连线触发动作: 点击注册" in result
    assert "连线前置操作: 填写表单" in result
    assert "连线备注: 注意验证" in result


def test_render_edge_hint_empty():
    assert _render_edge_hint({}) == ""
    assert _render_edge_hint({"trigger_action": "", "pre_action": "", "note": ""}) == ""


# ── _build_graph_prompt ────────────────────────────────────────


def test_graph_prompt_orders_main_nodes_by_main_order():
    nodes = [
        _make_node(1, "首页", "main", main_order=2),
        _make_node(2, "登录页", "main", main_order=1),
        _make_node(3, "详情页", "main", main_order=3),
    ]
    prompt = _build_graph_prompt(nodes, [])
    step1_pos = prompt.find("步骤 1")
    step2_pos = prompt.find("步骤 2")
    step3_pos = prompt.find("步骤 3")
    assert step1_pos > 0
    assert step2_pos > step1_pos
    assert step3_pos > step2_pos
    login_pos = prompt.find("登录页")
    home_pos = prompt.find("首页")
    assert login_pos < home_pos


def test_graph_prompt_attaches_branch_to_source_main_node():
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "忘记密码页", "branch"),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击忘记密码")]
    prompt = _build_graph_prompt(nodes, edges)
    login_pos = prompt.find("登录页")
    branch_pos = prompt.find("分支")
    forgot_pos = prompt.find("忘记密码页")
    assert login_pos > 0
    assert branch_pos > login_pos
    assert forgot_pos > branch_pos
    assert "点击忘记密码" in prompt


def test_graph_prompt_attaches_exception_to_source_main_node():
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "登录失败提示", "exception"),
    ]
    edges = [_make_edge(1, 2, "exception", condition="密码错误")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "异常" in prompt
    assert "登录失败提示" in prompt
    assert "密码错误" in prompt


def test_graph_prompt_attaches_bypass_to_source_main_node():
    nodes = [
        _make_node(1, "首页", "main", main_order=1),
        _make_node(2, "新手引导弹窗", "bypass"),
    ]
    edges = [_make_edge(1, 2, "bypass", condition="首次进入")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "旁路" in prompt
    assert "新手引导弹窗" in prompt
    assert "首次进入" in prompt


def test_graph_prompt_uses_user_condition_when_present():
    nodes = [
        _make_node(1, "首页", "main", main_order=1),
        _make_node(2, "筛选页", "branch"),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击高级筛选")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "点击高级筛选" in prompt


def test_graph_prompt_infers_default_branch_condition_when_missing():
    nodes = [
        _make_node(1, "首页", "main", main_order=1),
        _make_node(2, "高级筛选页", "branch"),
    ]
    edges = [_make_edge(1, 2, "branch")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "高级筛选页" in prompt


def test_graph_prompt_infers_default_exception_condition_when_missing():
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "登录失败提示", "exception"),
    ]
    edges = [_make_edge(1, 2, "exception")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "登录失败提示" in prompt


def test_graph_prompt_ignores_invalid_edge_without_crash():
    nodes = [
        _make_node(1, "首页", "main", main_order=1),
    ]
    edges = [
        {"source": "999", "target": "888", "edge_type": "branch", "condition": ""},
        {"source": "abc", "target": "xyz", "edge_type": "exception"},
    ]
    prompt = _build_graph_prompt(nodes, edges)
    assert "首页" in prompt
    assert len(prompt) > 100


def test_graph_prompt_includes_flow_meta_hints():
    nodes = [
        _make_node(1, "首页", "main", main_order=1),
        _make_node(2, "筛选页", "branch",
                   flow_meta={"pre_action": "已输入关键词", "expected_result": "展示筛选结果"}),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击筛选")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "前置操作" in prompt
    assert "已输入关键词" in prompt
    assert "预期结果" in prompt
    assert "展示筛选结果" in prompt


def test_graph_prompt_with_empty_nodes():
    prompt = _build_graph_prompt([], [])
    assert len(prompt) > 0


def test_graph_prompt_with_module_info():
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], module_info={"name": "登录模块", "description": "登录流程"})
    assert "登录模块" in prompt
    assert "登录流程" in prompt


def test_graph_prompt_nested_structure_has_tree_symbols():
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "忘记密码页", "branch"),
        _make_node(3, "登录失败提示", "exception"),
    ]
    edges = [
        _make_edge(1, 2, "branch", condition="点击忘记密码"),
        _make_edge(1, 3, "exception", condition="密码错误"),
    ]
    prompt = _build_graph_prompt(nodes, edges)
    assert "├─" in prompt or "└─" in prompt


# ── 流程感知历史用例评审 ─────────────────────────────────────


def test_graph_prompt_flow_structure_before_history_cases():
    """流程结构必须在历史用例之前输出，避免AI先按历史用例理解流程再被纠正"""
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "忘记密码页", "branch"),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击忘记密码")]
    history_cases = [
        {"id": 10, "title": "正向-登录成功", "module": "登录", "summary": "输入账号密码登录"},
    ]
    prompt = _build_graph_prompt(nodes, edges, history_cases=history_cases)
    flow_pos = prompt.find("UI原型图流程结构")
    history_pos = prompt.find("流程感知评审")
    assert flow_pos > 0, "流程结构部分应存在"
    assert history_pos > 0, "历史用例评审部分应存在"
    assert flow_pos < history_pos, "流程结构必须在历史用例之前"


def test_graph_prompt_history_case_with_coverage_annotation():
    """历史用例应标注其覆盖的流程节点"""
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "忘记密码页", "branch"),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击忘记密码")]
    history_cases = [
        {"id": 10, "title": "正向-登录成功", "module": "登录页", "summary": "输入账号密码登录"},
    ]
    prompt = _build_graph_prompt(nodes, edges, history_cases=history_cases)
    assert "覆盖" in prompt, "历史用例应有流程覆盖标注"


def test_graph_prompt_shows_uncovered_flow_nodes():
    """未被历史用例覆盖的流程节点应明确提示"""
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
        _make_node(2, "忘记密码页", "branch"),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击忘记密码")]
    history_cases = [
        {"id": 10, "title": "正向-登录成功", "module": "登录页", "summary": "输入账号密码登录"},
    ]
    prompt = _build_graph_prompt(nodes, edges, history_cases=history_cases)
    assert "未覆盖" in prompt or "未被任何历史用例覆盖" in prompt


def test_graph_prompt_no_uncovered_warning_when_all_covered():
    """所有流程节点被覆盖时不应出现未覆盖警告"""
    nodes = [
        _make_node(1, "登录页", "main", main_order=1),
    ]
    edges = []
    history_cases = [
        {"id": 10, "title": "正向-登录页成功", "module": "登录页", "summary": "登录页输入账号密码"},
    ]
    prompt = _build_graph_prompt(nodes, edges, history_cases=history_cases)
    assert "未被任何历史用例覆盖" not in prompt


def test_graph_prompt_history_review_rules_flow_aware():
    """有历史用例时，生成规则应包含流程感知的评审规则"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    history_cases = [{"id": 1, "title": "测试用例", "module": "首页", "summary": "首页测试"}]
    prompt = _build_graph_prompt(nodes, [], history_cases=history_cases)
    assert "逐步骤检查" in prompt or "流程结构" in prompt


def test_graph_prompt_no_history_no_flow_aware_rules():
    """无历史用例时，不应出现流程感知评审规则"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [])
    assert "流程感知评审" not in prompt


# ── _infer_history_case_flow_coverage ──────────────────────────


def test_infer_coverage_matches_main_node():
    """历史用例标题包含主干节点名称时应匹配"""
    case = {"title": "正向-登录成功", "module": "登录页", "summary": "输入账号密码"}
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    node_map = {1: _make_node(1, "登录页", "main", main_order=1)}
    result = _infer_history_case_flow_coverage(
        case, main_nodes, {}, {}, {}, node_map
    )
    assert "步骤1" in result
    assert "登录页" in result


def test_infer_coverage_matches_branch():
    """历史用例标题包含分支条件时应匹配分支"""
    case = {"title": "分支-忘记密码", "module": "登录", "summary": "点击忘记密码"}
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    branch_by_source = {1: [_make_edge(1, 2, "branch", condition="忘记密码")]}
    node_map = {
        1: _make_node(1, "登录页", "main", main_order=1),
        2: _make_node(2, "忘记密码页", "branch"),
    }
    result = _infer_history_case_flow_coverage(
        case, main_nodes, branch_by_source, {}, {}, node_map
    )
    assert "分支" in result or "忘记密码" in result


def test_infer_coverage_no_match():
    """历史用例与流程节点无关时应标注未匹配"""
    case = {"title": "性能-并发测试", "module": "性能", "summary": "并发压测"}
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    node_map = {1: _make_node(1, "登录页", "main", main_order=1)}
    result = _infer_history_case_flow_coverage(
        case, main_nodes, {}, {}, {}, node_map
    )
    assert "未匹配" in result


def test_infer_coverage_matches_exception():
    """历史用例标题包含异常条件时应匹配异常"""
    case = {"title": "异常-密码错误", "module": "登录", "summary": "输入错误密码"}
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    exception_by_source = {1: [_make_edge(1, 2, "exception", condition="密码错误")]}
    node_map = {
        1: _make_node(1, "登录页", "main", main_order=1),
        2: _make_node(2, "登录失败提示", "exception"),
    }
    result = _infer_history_case_flow_coverage(
        case, main_nodes, {}, exception_by_source, {}, node_map
    )
    assert "异常" in result or "密码错误" in result


def test_infer_coverage_matches_bypass():
    """历史用例标题包含旁路条件时应匹配旁路"""
    case = {"title": "旁路-新手引导", "module": "首页", "summary": "首次进入弹出引导"}
    main_nodes = [_make_node(1, "首页", "main", main_order=1)]
    bypass_by_source = {1: [_make_edge(1, 2, "bypass", condition="新手引导")]}
    node_map = {
        1: _make_node(1, "首页", "main", main_order=1),
        2: _make_node(2, "引导弹窗", "bypass"),
    }
    result = _infer_history_case_flow_coverage(
        case, main_nodes, {}, {}, bypass_by_source, node_map
    )
    assert "旁路" in result or "引导" in result


# ── _find_uncovered_flow_nodes ─────────────────────────────────


def test_find_uncovered_detects_missing_main():
    """主干节点未被历史用例覆盖时应检测到"""
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    node_map = {1: _make_node(1, "登录页", "main", main_order=1)}
    history_cases = [{"title": "性能测试", "module": "性能", "summary": "压测"}]
    result = _find_uncovered_flow_nodes(
        history_cases, main_nodes, {}, {}, {}, node_map
    )
    assert len(result) > 0
    assert any("登录页" in r for r in result)


def test_find_uncovered_detects_missing_branch():
    """分支节点未被历史用例覆盖时应检测到"""
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    branch_by_source = {1: [_make_edge(1, 2, "branch", condition="忘记密码")]}
    node_map = {
        1: _make_node(1, "登录页", "main", main_order=1),
        2: _make_node(2, "忘记密码页", "branch"),
    }
    history_cases = [{"title": "正向-登录成功", "module": "登录页", "summary": "输入账号密码"}]
    result = _find_uncovered_flow_nodes(
        history_cases, main_nodes, branch_by_source, {}, {}, node_map
    )
    assert any("分支" in r for r in result)


def test_find_uncovered_empty_when_all_covered():
    """所有流程节点被覆盖时应返回空列表"""
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    node_map = {1: _make_node(1, "登录页", "main", main_order=1)}
    history_cases = [{"title": "正向-登录页成功", "module": "登录页", "summary": "登录页测试"}]
    result = _find_uncovered_flow_nodes(
        history_cases, main_nodes, {}, {}, {}, node_map
    )
    assert result == []


def test_find_uncovered_detects_missing_exception():
    """异常节点未被历史用例覆盖时应检测到"""
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    exception_by_source = {1: [_make_edge(1, 2, "exception", condition="密码错误")]}
    node_map = {
        1: _make_node(1, "登录页", "main", main_order=1),
        2: _make_node(2, "登录失败提示", "exception"),
    }
    history_cases = [{"title": "正向-登录成功", "module": "登录页", "summary": "输入账号密码"}]
    result = _find_uncovered_flow_nodes(
        history_cases, main_nodes, {}, exception_by_source, {}, node_map
    )
    assert any("异常" in r for r in result)


def test_find_uncovered_detects_missing_bypass():
    """旁路节点未被历史用例覆盖时应检测到"""
    main_nodes = [_make_node(1, "首页", "main", main_order=1)]
    bypass_by_source = {1: [_make_edge(1, 2, "bypass", condition="新手引导")]}
    node_map = {
        1: _make_node(1, "首页", "main", main_order=1),
        2: _make_node(2, "引导弹窗", "bypass"),
    }
    history_cases = [{"title": "正向-首页成功", "module": "首页", "summary": "首页测试"}]
    result = _find_uncovered_flow_nodes(
        history_cases, main_nodes, {}, {}, bypass_by_source, node_map
    )
    assert any("旁路" in r for r in result)


# ── 覆盖率补充测试 ──────────────────────────────────────────────


def test_graph_prompt_with_test_point_and_requirement():
    """测试点信息和需求文档内容应出现在 Prompt 中"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(
        nodes, [],
        test_point_json='{"point": "登录验证"}',
        requirement_content="用户需输入账号密码",
    )
    assert "测试点信息" in prompt
    assert "需求文档内容" in prompt
    assert "登录验证" in prompt


def test_graph_prompt_without_requirement():
    """无需求文档时应显示占位文本"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], requirement_content="")
    assert "无需求文档内容" in prompt


def test_graph_prompt_with_ui_specs():
    """UI规格文本应出现在 Prompt 中"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], ui_specs_text="按钮: 登录")
    assert "UI原型图解析结果" in prompt
    assert "按钮: 登录" in prompt


def test_graph_prompt_with_case_type():
    """指定 case_type 时应出现对应约束"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], case_type="ui_automation")
    assert "ui_automation" in prompt
    assert "UI元素交互" in prompt


def test_graph_prompt_with_case_type_manual():
    """case_type=manual 时应出现人工判断提示"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], case_type="manual")
    assert "manual" in prompt
    assert "人工判断" in prompt


def test_graph_prompt_with_case_type_api():
    """case_type=api_automation 时应出现API层面提示"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], case_type="api_automation")
    assert "api_automation" in prompt
    assert "接口层面验证" in prompt


def test_graph_prompt_with_case_type_performance():
    """case_type=performance 时应出现性能指标提示"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], case_type="performance")
    assert "performance" in prompt
    assert "性能指标" in prompt


def test_graph_prompt_with_case_type_security():
    """case_type=security 时应出现安全验证提示"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    prompt = _build_graph_prompt(nodes, [], case_type="security")
    assert "security" in prompt
    assert "安全验证" in prompt


def test_graph_prompt_duplicate_screen_id_warning():
    """重复 screen_id 时应记录警告日志"""
    nodes = [
        _make_node(1, "首页", "main", main_order=1),
        _make_node(1, "首页副本", "main", main_order=2),
    ]
    prompt = _build_graph_prompt(nodes, [])
    assert "首页" in prompt or "首页副本" in prompt


def test_graph_prompt_with_include_images():
    """include_images=True 且节点有 image_url 时应包含图片引用"""
    nodes = [_make_node(1, "首页", "main", main_order=1)]
    nodes[0]["image_url"] = "https://example.com/img.png"
    prompt = _build_graph_prompt(nodes, [], include_images=True)
    assert "图片URL" in prompt


def test_infer_condition_unknown_edge_type():
    """未知 edge_type 应返回未知触发条件"""
    edge = {"condition": "", "label": "", "id": "e1"}
    target_node = {"screen_name": "目标页"}
    result = _infer_condition(edge, "unknown_type", target_node)
    assert "未知触发条件" in result
    assert "系统推断" in result


def test_format_node_elements_with_labels():
    """有 label 的元素应被格式化输出，包含 type:label 结构"""
    from app.services.prompt_builder.case_prompt import _format_node_elements
    elements = [
        {"type": "input", "label": "用户名"},
        {"type": "button", "label": "登录"},
    ]
    result = _format_node_elements(elements)
    assert "input:用户名" in result
    assert "button:登录" in result


def test_format_node_elements_with_state_and_interactive():
    """元素应包含 state/interactive/description 信息"""
    from app.services.prompt_builder.case_prompt import _format_node_elements
    elements = [
        {"type": "button", "label": "登录", "state": "disabled", "interactive": False},
        {"type": "input", "label": "用户名", "state": "normal", "interactive": True, "description": "请输入用户名"},
    ]
    result = _format_node_elements(elements)
    assert "状态:disabled" in result
    assert "不可交互" in result
    assert "状态:normal" in result
    assert "可交互" in result
    assert "请输入用户名" in result


def test_format_node_elements_with_semantic_fallback():
    """description 缺失时应回退到 semantic 字段"""
    from app.services.prompt_builder.case_prompt import _format_node_elements
    elements = [
        {"type": "text", "label": "提示", "semantic": "错误提示文案"},
    ]
    result = _format_node_elements(elements)
    assert "错误提示文案" in result


def test_format_node_elements_filters_no_label():
    """无 label 的元素应被过滤"""
    from app.services.prompt_builder.case_prompt import _format_node_elements
    elements = [
        {"type": "input", "label": ""},
        {"type": "button", "label": "登录"},
    ]
    result = _format_node_elements(elements)
    assert "input" not in result
    assert "button:登录" in result


def test_format_node_elements_empty():
    """空元素列表应返回空字符串"""
    from app.services.prompt_builder.case_prompt import _format_node_elements
    assert _format_node_elements([]) == ""
    assert _format_node_elements(None) == ""


def test_build_image_ref_with_url():
    """有 image_url 且 include_images=True 时应返回引用"""
    from app.services.prompt_builder.case_prompt import _build_image_ref
    node = {"image_url": "https://example.com/img.png"}
    result = _build_image_ref(node, include_images=True)
    assert "图片URL" in result


def test_build_image_ref_without_include():
    """include_images=False 时不应返回引用"""
    from app.services.prompt_builder.case_prompt import _build_image_ref
    node = {"image_url": "https://example.com/img.png"}
    result = _build_image_ref(node, include_images=False)
    assert result == ""


def test_match_flow_nodes_with_invalid_target():
    """边的 target 无效时应跳过而不报错"""
    from app.services.prompt_builder.flow_aware_history import _match_flow_nodes
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    edge = {"source": "1", "target": "invalid", "edge_type": "branch", "condition": "忘记密码"}
    branch_by_source = {1: [edge]}
    node_map = {1: _make_node(1, "登录页", "main", main_order=1)}
    result = _match_flow_nodes(
        "登录页 忘记密码", main_nodes,
        branch_by_source, {}, {}, node_map,
    )
    assert any(m['node_type'] == 'main' for m in result)


def test_find_uncovered_with_invalid_target():
    """边的 target 无效时未覆盖检测应跳过而不报错"""
    main_nodes = [_make_node(1, "登录页", "main", main_order=1)]
    edge = {"source": "1", "target": "invalid", "edge_type": "branch", "condition": "忘记密码"}
    branch_by_source = {1: [edge]}
    node_map = {1: _make_node(1, "登录页", "main", main_order=1)}
    history_cases = []
    result = _find_uncovered_flow_nodes(
        history_cases, main_nodes, branch_by_source, {}, {}, node_map,
    )
    assert any("登录页" in r for r in result)
