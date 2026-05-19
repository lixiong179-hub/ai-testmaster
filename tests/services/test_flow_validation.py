import pytest
from app.services.flow_validation import validate_flow_structure


class TestValidateFlowStructure:
    def test_empty_nodes_returns_error(self):
        errors, warnings = validate_flow_structure([], [])
        assert len(errors) == 1
        assert "节点列表为空" in errors[0]

    def test_no_main_node_returns_error(self):
        nodes = [{"screen_id": 1, "flow_type": "branch", "screen_name": "A"}]
        errors, warnings = validate_flow_structure(nodes, [])
        assert any("主干节点" in e for e in errors)

    def test_valid_main_node_no_errors(self):
        nodes = [{"screen_id": 1, "flow_type": "main", "screen_name": "A"}]
        edges = []
        errors, warnings = validate_flow_structure(nodes, edges)
        assert len(errors) == 0

    def test_edge_missing_target(self):
        nodes = [{"screen_id": 1, "flow_type": "main", "screen_name": "A"}]
        edges = [{"source": 1, "edge_type": "normal"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("缺少 target" in e for e in errors)

    def test_edge_points_to_nonexistent_node(self):
        nodes = [{"screen_id": 1, "flow_type": "main", "screen_name": "A"}]
        edges = [{"source": 1, "target": 999, "edge_type": "normal"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("不存在的节点" in e for e in errors)

    def test_edge_source_nonexistent(self):
        nodes = [{"screen_id": 1, "flow_type": "main", "screen_name": "A"}]
        edges = [{"source": 999, "target": 1, "edge_type": "normal"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("不存在的节点" in e for e in errors)

    def test_branch_edge_missing_condition_warning(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "branch", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "branch"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("缺少触发条件" in w for w in warnings)

    def test_exception_edge_missing_condition_warning(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "main", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "exception"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("缺少触发条件" in w for w in warnings)

    def test_bypass_edge_missing_condition_warning(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "main", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "bypass"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("旁路" in w for w in warnings)

    def test_multiple_main_nodes_no_normal_edges_warning(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "main", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "branch"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert any("正常连线" in w for w in warnings)

    def test_isolated_node_warning(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "main", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "normal"}]
        _, warnings = validate_flow_structure(nodes, edges)
        isolated = [w for w in warnings if "孤立" in w]
        assert len(isolated) == 0

    def test_fully_valid_flow(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "main", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "normal"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert len(errors) == 0

    def test_branch_with_condition_no_warning(self):
        nodes = [
            {"screen_id": 1, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 2, "flow_type": "branch", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 2, "edge_type": "branch", "condition": "金额>100"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert not any("缺少触发条件" in w for w in warnings)

    def test_target_zero_is_valid(self):
        nodes = [
            {"screen_id": 0, "flow_type": "main", "screen_name": "A"},
            {"screen_id": 1, "flow_type": "main", "screen_name": "B"},
        ]
        edges = [{"source": 1, "target": 0, "edge_type": "normal"}]
        errors, warnings = validate_flow_structure(nodes, edges)
        assert not any("缺少 target" in e for e in errors)
