import pytest
from app.services.lineage_service import (
    get_lineage,
    _to_node,
    _check_chain_warning,
    LineageNode,
    LineageResult,
    MAX_DESCENDANT_DEPTH,
)
from app.models.test_case import TestCase


def _make_case(db, testProject, case_no, title, parent_case_id=None):
    case = TestCase(
        project_id=testProject.id, title=title,
        case_no=case_no, lifecycle_status="active",
        module="测试模块", precondition="无",
        steps_json=[{"step": 1, "action": "操作", "param": ""}],
        expected_result="成功", priority=2, case_type="UI",
        parent_case_id=parent_case_id,
    )
    db.add(case)
    db.flush()
    return case


class TestToNode:
    def test_converts_test_case(self, db, testProject):
        case = _make_case(db, testProject, "LIN-001", "lineage_case")
        node = _to_node(case)
        assert node.id == case.id
        assert node.case_no == "LIN-001"
        assert node.title == "lineage_case"
        assert node.lifecycle_status == "active"


class TestCheckChainWarning:
    def test_short_chain_no_warning(self):
        result = _check_chain_warning(1)
        assert result is None

    def test_long_chain_warning(self):
        result = _check_chain_warning(5)
        assert result is not None
        assert "警告阈值" in result

    def test_exact_threshold_warning(self):
        result = _check_chain_warning(3)
        assert result is not None


class TestGetLineage:
    def test_nonexistent_case(self, db):
        result = get_lineage(db, 99999)
        assert result is None

    def test_case_no_parent(self, db, testProject):
        case = _make_case(db, testProject, "ROOT-001", "root_case")
        result = get_lineage(db, case.id)
        assert result is not None
        assert result.chain_length == 1
        assert len(result.ancestors) == 0

    def test_case_with_parent(self, db, testProject):
        parent = _make_case(db, testProject, "PAR-001", "parent_case")
        child = _make_case(db, testProject, "CHI-001", "child_case", parent_case_id=parent.id)
        result = get_lineage(db, child.id)
        assert result is not None
        assert result.chain_length == 2
        assert len(result.ancestors) == 1


class TestLineageNode:
    def test_create_node(self):
        node = LineageNode(id=1, case_no="T-001", title="test", lifecycle_status="active")
        assert node.id == 1
        assert node.children == []


class TestLineageResult:
    def test_create_result(self):
        root = LineageNode(id=1, case_no="T-001", title="root", lifecycle_status="active")
        result = LineageResult(root=root, chain_length=1)
        assert result.chain_length == 1
        assert result.warning is None


class TestMaxDescendantDepth:
    def test_depth_limit(self):
        assert MAX_DESCENDANT_DEPTH == 10
