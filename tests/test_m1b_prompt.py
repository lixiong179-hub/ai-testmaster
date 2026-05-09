"""M1B Prompt enhancement tests."""
import pytest
from app.services.prompt_builder import (
    PromptBuilder, _infer_condition, _render_flow_meta_hint, _group_edges_by_source,
)


class TestInferCondition:
    def test_explicit(self):
        assert _infer_condition({'condition': '点击注册', 'label': ''}, 'branch', {'screen_name': '注册�?}) == '点击注册'

    def test_branch_infer_with_source_node(self):
        r = _infer_condition({'condition': '', 'label': ''}, 'branch', {'screen_name': '忘记密码�?}, {'screen_name': '登录�?})
        assert '登录�? in r and '忘记密码�? in r

    def test_branch_infer_fallback_to_label(self):
        r = _infer_condition({'condition': '', 'label': '忘记密码'}, 'branch', {'screen_name': '忘记密码�?})
        assert '忘记密码' in r

    def test_exception_infer(self):
        r = _infer_condition({'condition': '', 'label': ''}, 'exception', {'screen_name': '错误�?})
        assert '错误�? in r and '异常' in r

    def test_bypass_infer(self):
        r = _infer_condition({'condition': '', 'label': ''}, 'bypass', {'screen_name': '弹窗'}, {'screen_name': '首页'})
        assert '首页' in r and '弹窗' in r

    def test_none_condition(self):
        r = _infer_condition({'condition': None, 'label': ''}, 'branch', {'screen_name': '目标'})
        assert '目标' in r


class TestRenderFlowMetaHint:
    def test_empty(self):
        assert _render_flow_meta_hint({}, 'branch') == ''

    def test_pre_action(self):
        assert '前置操作: 点击' in _render_flow_meta_hint({'pre_action': '点击'}, 'branch')

    def test_bypass_reason_type_check(self):
        assert '旁路原因' not in _render_flow_meta_hint({'bypass_reason': '广告'}, 'branch')
        assert '旁路原因: 广告' in _render_flow_meta_hint({'bypass_reason': '广告'}, 'bypass')

    def test_multiple(self):
        r = _render_flow_meta_hint({'pre_action': 'a', 'expected_result': 'b'}, 'branch')
        assert '前置操作: a' in r and '预期结果: b' in r


class TestGroupEdgesBySource:
    def test_empty(self):
        assert _group_edges_by_source([]) == {}

    def test_grouping(self):
        r = _group_edges_by_source([{'source': '1', 'target': '2'}, {'source': '1', 'target': '3'}])
        assert len(r[1]) == 2

    def test_invalid_skipped(self):
        assert _group_edges_by_source([{'source': 'bad', 'target': '2'}]) == {}


class TestNestedPrompt:
    def test_branch_nested(self):
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '登录�?, 'ui_spec_elements': []},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'main', 'screen_name': '首页', 'ui_spec_elements': []},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'branch', 'screen_name': '忘记密码�?, 'ui_spec_elements': []},
        ]
        edges = [{'source': '1', 'target': '3', 'edge_type': 'branch', 'condition': '点击忘记密码', 'label': ''}]
        r = PromptBuilder.build_graph_prompt(nodes=nodes, edges=edges, module_info={'name': '', 'description': ''}, requirement_content='', test_point_json='{}', ui_specs_text='')
        lines = r.split('\n')
        s1 = next((i for i, l in enumerate(lines) if '步骤 1:' in l), None)
        br = next((i for i, l in enumerate(lines) if '└─ 分支 A:' in l), None)
        assert s1 is not None and br is not None and br > s1

    def test_flow_meta_in_prompt(self):
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '登录�?, 'ui_spec_elements': []},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'exception', 'screen_name': '错误�?, 'ui_spec_elements': [], 'flow_meta': {'pre_action': '输错密码'}},
        ]
        edges = [{'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': '密码错误', 'label': ''}]
        r = PromptBuilder.build_graph_prompt(nodes=nodes, edges=edges, module_info={'name': '', 'description': ''}, requirement_content='', test_point_json='{}', ui_specs_text='')
        assert '前置操作: 输错密码' in r

    def test_mixed_types_under_step(self):
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '登录�?, 'ui_spec_elements': []},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'branch', 'screen_name': '注册�?, 'ui_spec_elements': []},
            {'screen_id': 3, 'screen_order': 3, 'flow_type': 'exception', 'screen_name': '错误�?, 'ui_spec_elements': []},
            {'screen_id': 4, 'screen_order': 4, 'flow_type': 'bypass', 'screen_name': '弹窗', 'ui_spec_elements': []},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'branch', 'condition': '点击注册', 'label': ''},
            {'source': '1', 'target': '3', 'edge_type': 'exception', 'condition': '密码错误', 'label': ''},
            {'source': '1', 'target': '4', 'edge_type': 'bypass', 'condition': '自动弹出', 'label': ''},
        ]
        r = PromptBuilder.build_graph_prompt(nodes=nodes, edges=edges, module_info={'name': '', 'description': ''}, requirement_content='', test_point_json='{}', ui_specs_text='')
        # Dynamic tree: branch ├─, exception ├─, bypass └─ (last child)
        assert '├─ 分支 A:' in r and '├─ 异常 A:' in r and '└─ 旁路 A:' in r

    def test_single_child_uses_end_symbol(self):
        nodes = [
            {'screen_id': 1, 'screen_order': 1, 'flow_type': 'main', 'screen_name': '登录�?, 'ui_spec_elements': []},
            {'screen_id': 2, 'screen_order': 2, 'flow_type': 'branch', 'screen_name': '注册�?, 'ui_spec_elements': []},
        ]
        edges = [
            {'source': '1', 'target': '2', 'edge_type': 'branch', 'condition': '点击注册', 'label': ''},
        ]
        r = PromptBuilder.build_graph_prompt(nodes=nodes, edges=edges, module_info={'name': '', 'description': ''}, requirement_content='', test_point_json='{}', ui_specs_text='')
        # Single child should use └─
        assert '└─ 分支 A:' in r
