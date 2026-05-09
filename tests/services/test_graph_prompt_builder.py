"""Graph Prompt 构建器单元测试�?
覆盖:
    - 主干节点�?main_order 排序输出
    - 分支/异常/旁路挂载到对应源主干节点�?    - 用户填写条件优先使用
    - 缺少条件时自动推�?    - 无效边不导致异常
    - flow_meta 补充信息渲染
    - 推断条件标注来源
"""
import pytest

from app.services.prompt_builder.case_prompt import _build_graph_prompt
from app.services.prompt_builder.helpers import (
    _infer_condition,
    _render_flow_meta_hint,
    _safe_int,
    _group_edges_by_source,
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


# ── _infer_condition ───────────────────────────────────────────


def test_infer_condition_uses_user_condition_first():
    edge = _make_edge(1, 2, "branch", condition="点击高级筛�?)
    target = _make_node(2, "高级筛选页", "branch")
    result = _infer_condition(edge, "branch", target)
    assert "点击高级筛�? in result
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
    target = _make_node(2, "登录失败�?, "exception")
    source = _make_node(1, "登录�?, "main")
    result = _infer_condition(edge, "exception", target, source)
    assert "登录失败�? in result


def test_infer_condition_bypass_default():
    edge = _make_edge(1, 2, "bypass")
    target = _make_node(2, "引导弹窗", "bypass")
    source = _make_node(1, "首页", "main")
    result = _infer_condition(edge, "bypass", target, source)
    assert "引导弹窗" in result


def test_infer_condition_uses_edge_label_when_no_condition():
    edge = _make_edge(1, 2, "branch", label="分支：点击详�?)
    target = _make_node(2, "详情�?, "branch")
    result = _infer_condition(edge, "branch", target)
    assert "点击详情" in result or "详情�? in result


# ── _render_flow_meta_hint ─────────────────────────────────────


def test_render_flow_meta_hint_with_pre_action():
    meta = {"pre_action": "已输入搜索条�?}
    result = _render_flow_meta_hint(meta, "branch")
    assert "前置操作" in result
    assert "已输入搜索条�? in result


def test_render_flow_meta_hint_with_expected_result():
    meta = {"expected_result": "展示高级筛选面�?}
    result = _render_flow_meta_hint(meta, "branch")
    assert "预期结果" in result
    assert "展示高级筛选面�? in result


def test_render_flow_meta_hint_with_bypass_reason():
    meta = {"bypass_reason": "首次进入自动弹出"}
    result = _render_flow_meta_hint(meta, "bypass")
    assert "旁路原因" in result
    assert "首次进入自动弹出" in result


def test_render_flow_meta_hint_with_note():
    meta = {"note": "需要校验弹窗关�?}
    result = _render_flow_meta_hint(meta, "branch")
    assert "备注" in result
    assert "需要校验弹窗关�? in result


def test_render_flow_meta_hint_empty():
    assert _render_flow_meta_hint({}, "branch") == ""
    assert _render_flow_meta_hint({"irrelevant": "value"}, "branch") == ""


# ── _build_graph_prompt ────────────────────────────────────────


def test_graph_prompt_orders_main_nodes_by_main_order():
    nodes = [
        _make_node(1, "首页", "main", main_order=2),
        _make_node(2, "登录�?, "main", main_order=1),
        _make_node(3, "详情�?, "main", main_order=3),
    ]
    prompt = _build_graph_prompt(nodes, [])
    step1_pos = prompt.find("步骤 1")
    step2_pos = prompt.find("步骤 2")
    step3_pos = prompt.find("步骤 3")
    assert step1_pos > 0
    assert step2_pos > step1_pos
    assert step3_pos > step2_pos
    login_pos = prompt.find("登录�?)
    home_pos = prompt.find("首页")
    assert login_pos < home_pos


def test_graph_prompt_attaches_branch_to_source_main_node():
    nodes = [
        _make_node(1, "登录�?, "main", main_order=1),
        _make_node(2, "忘记密码�?, "branch"),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击忘记密码")]
    prompt = _build_graph_prompt(nodes, edges)
    login_pos = prompt.find("登录�?)
    branch_pos = prompt.find("分支")
    forgot_pos = prompt.find("忘记密码�?)
    assert login_pos > 0
    assert branch_pos > login_pos
    assert forgot_pos > branch_pos
    assert "点击忘记密码" in prompt


def test_graph_prompt_attaches_exception_to_source_main_node():
    nodes = [
        _make_node(1, "登录�?, "main", main_order=1),
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
    edges = [_make_edge(1, 2, "branch", condition="点击高级筛�?)]
    prompt = _build_graph_prompt(nodes, edges)
    assert "点击高级筛�? in prompt


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
        _make_node(1, "登录�?, "main", main_order=1),
        _make_node(2, "登录失败�?, "exception"),
    ]
    edges = [_make_edge(1, 2, "exception")]
    prompt = _build_graph_prompt(nodes, edges)
    assert "登录失败�? in prompt


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
                   flow_meta={"pre_action": "已输入关键词", "expected_result": "展示筛选结�?}),
    ]
    edges = [_make_edge(1, 2, "branch", condition="点击筛�?)]
    prompt = _build_graph_prompt(nodes, edges)
    assert "前置操作" in prompt
    assert "已输入关键词" in prompt
    assert "预期结果" in prompt
    assert "展示筛选结�? in prompt


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
        _make_node(1, "登录�?, "main", main_order=1),
        _make_node(2, "忘记密码�?, "branch"),
        _make_node(3, "登录失败提示", "exception"),
    ]
    edges = [
        _make_edge(1, 2, "branch", condition="点击忘记密码"),
        _make_edge(1, 3, "exception", condition="密码错误"),
    ]
    prompt = _build_graph_prompt(nodes, edges)
    assert "├─" in prompt or "└─" in prompt
