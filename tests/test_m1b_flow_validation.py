"""M1B-6 后端流程结构校验单元测试"""
import pytest
from app.services.flow_validation import validate_flow_structure


class TestFlowValidationErrors:
    def test_empty_nodes(self):
        errors, warnings = validate_flow_structure([], [])
        assert len(errors) >= 1
        assert any('节点列表为空' in e for e in errors)

    def test_no_main_nodes(self):
        nodes = [{'screen_id': 1, 'flow_type': 'branch', 'screen_name': 'B'}]
        errors, warnings = validate_flow_structure(nodes, [])
        assert any('主干节点' in e for e in errors)

    def test_edge_missing_target(self):
        nodes = [{'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M'}]
        edges = [{'source': '1', 'target': '', 'edge_type': 'branch', 'condition': ''}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('缺少 target' in e for e in errors)

    def test_normal_edge_missing_target(self):
        nodes = [{'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M1'},
                  {'screen_id': 2, 'flow_type': 'main', 'screen_name': 'M2'}]
        edges = [{'source': '1', 'target': '', 'edge_type': 'normal', 'condition': ''}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('缺少 target' in e for e in errors)

    def test_edge_points_to_nonexistent_node(self):
        nodes = [{'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M'}]
        edges = [{'source': '1', 'target': '99', 'edge_type': 'branch', 'condition': 'c'}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('不存在的节点' in e for e in errors)

    def test_edge_source_nonexistent(self):
        nodes = [{'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M'}]
        edges = [{'source': '99', 'target': '1', 'edge_type': 'normal', 'condition': ''}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('不存在的节点' in e for e in errors)


class TestFlowValidationWarnings:
    def test_multiple_main_no_normal_edges(self):
        nodes = [
            {'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M1'},
            {'screen_id': 2, 'flow_type': 'main', 'screen_name': 'M2'},
        ]
        errors, warnings = validate_flow_structure(nodes, [])
        assert any('正常连线' in w for w in warnings)

    def test_branch_missing_condition(self):
        nodes = [
            {'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M'},
            {'screen_id': 2, 'flow_type': 'branch', 'screen_name': 'B'},
        ]
        edges = [{'source': '1', 'target': '2', 'edge_type': 'branch', 'condition': ''}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('缺少触发条件' in w for w in warnings)

    def test_exception_missing_condition(self):
        nodes = [
            {'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M'},
            {'screen_id': 2, 'flow_type': 'exception', 'screen_name': 'E'},
        ]
        edges = [{'source': '1', 'target': '2', 'edge_type': 'exception', 'condition': ''}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('缺少触发条件' in w for w in warnings)

    def test_orphan_node(self):
        nodes = [
            {'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M1'},
            {'screen_id': 2, 'flow_type': 'main', 'screen_name': 'M2'},
        ]
        edges = [{'source': '1', 'target': '2', 'edge_type': 'normal', 'condition': ''}]
        # M2 is connected via edge, but add an orphan
        nodes.append({'screen_id': 3, 'flow_type': 'branch', 'screen_name': 'Orphan'})
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any('孤立节点' in w for w in warnings)


class TestFlowValidationValid:
    def test_valid_flow_no_issues(self):
        nodes = [
            {'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M1'},
            {'screen_id': 2, 'flow_type': 'main', 'screen_name': 'M2'},
        ]
        edges = [{'source': '1', 'target': '2', 'edge_type': 'normal', 'condition': ''}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert len(errors) == 0

    def test_valid_branch_with_condition(self):
        nodes = [
            {'screen_id': 1, 'flow_type': 'main', 'screen_name': 'M'},
            {'screen_id': 2, 'flow_type': 'branch', 'screen_name': 'B'},
        ]
        edges = [{'source': '1', 'target': '2', 'edge_type': 'branch', 'condition': '点击'}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert not any('缺少触发条件' in w for w in warnings)
