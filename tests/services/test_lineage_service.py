"""M4-T03 用例血缘服务单元测试

覆盖率 —    - get_lineage 正常查询（根节点/中间节点/叶子节点）    - 祖先链追溯（多级/无祖先、循环引用）    - 后代子树构建（单层/多层/无后代）
    - 链长度警告（阈值触发/未触发）
    - 用例不存在返回 None
"""
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.test_case import TestCase, Base as TestCaseBase
from app.services.lineage_service import (
    get_lineage, _trace_ancestors, _build_descendant_tree,
    _to_node, _check_chain_warning, LineageNode, LineageResult,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    TestCaseBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_case(
    db, case_no: str, title: str, parent_case_id=None,
    lifecycle_status="active", prior_score=None, posterior_score=None,
) -> TestCase:
    case = TestCase(
        case_no=case_no,
        project_id=1,
        module="test",
        title=title,
        precondition="none",
        steps_json=[],
        expected_result="pass",
        priority=2,
        case_type="API",
        lifecycle_status=lifecycle_status,
        parent_case_id=parent_case_id,
        prior_quality_score=prior_score,
        posterior_quality_score=posterior_score,
    )
    db.add(case)
    db.flush()
    return case


class TestGetLineage:
    def test_root_case_no_ancestors(self, db):
        root = _make_case(db, "P1-C001", "根用例")
        result = get_lineage(db, root.id)
        assert result is not None
        assert result.root.id == root.id
        assert result.ancestors == []
        assert result.chain_length == 1

    def test_case_with_parent(self, db):
        parent = _make_case(db, "P1-C001", "父用例")
        child = _make_case(db, "P1-C001-v2", "子用例", parent_case_id=parent.id)
        result = get_lineage(db, child.id)
        assert result is not None
        assert len(result.ancestors) == 1
        assert result.ancestors[0].id == parent.id
        assert result.chain_length == 2

    def test_three_level_chain(self, db):
        root = _make_case(db, "P1-C001", "根用例")
        mid = _make_case(db, "P1-C001-v2", "中间用例", parent_case_id=root.id)
        leaf = _make_case(db, "P1-C001-v3", "叶子用例", parent_case_id=mid.id)
        result = get_lineage(db, leaf.id)
        assert result is not None
        assert len(result.ancestors) == 2
        assert result.ancestors[0].id == root.id
        assert result.ancestors[1].id == mid.id
        assert result.chain_length == 3

    def test_case_not_found(self, db):
        result = get_lineage(db, 99999)
        assert result is None

    def test_descendants_in_root(self, db):
        root = _make_case(db, "P1-C001", "根用例")
        child1 = _make_case(db, "P1-C001-v2", "子", parent_case_id=root.id)
        child2 = _make_case(db, "P1-C001-v3", "子", parent_case_id=root.id)
        result = get_lineage(db, root.id)
        assert result is not None
        assert len(result.root.children) == 2
        child_ids = {c.id for c in result.root.children}
        assert child1.id in child_ids
        assert child2.id in child_ids

    def test_multi_level_descendants(self, db):
        root = _make_case(db, "P1-C001", "根用例")
        child = _make_case(db, "P1-C001-v2", "子", parent_case_id=root.id)
        grandchild = _make_case(db, "P1-C001-v3", "子", parent_case_id=child.id)
        result = get_lineage(db, root.id)
        assert len(result.root.children) == 1
        assert len(result.root.children[0].children) == 1
        assert result.root.children[0].children[0].id == grandchild.id


class TestTraceAncestors:
    def test_no_parent(self, db):
        case = _make_case(db, "P1-C001", "根用例")
        ancestors = _trace_ancestors(db, case)
        assert ancestors == []

    def test_single_parent(self, db):
        parent = _make_case(db, "P1-C001", "父用例")
        child = _make_case(db, "P1-C001-v2", "子用例", parent_case_id=parent.id)
        ancestors = _trace_ancestors(db, child)
        assert len(ancestors) == 1
        assert ancestors[0].id == parent.id

    def test_circular_reference_breaks(self, db):
        case1 = _make_case(db, "P1-C001", "用例1")
        case2 = _make_case(db, "P1-C002", "用例2", parent_case_id=case1.id)
        case1.parent_case_id = case2.id
        db.flush()
        ancestors = _trace_ancestors(db, case1)
        assert len(ancestors) <= 2


class TestBuildDescendantTree:
    def test_no_children(self, db):
        case = _make_case(db, "P1-C001", "叶子用例")
        node = _to_node(case)
        _build_descendant_tree(db, node)
        assert node.children == []

    def test_with_children(self, db):
        root = _make_case(db, "P1-C001", "根用例")
        _make_case(db, "P1-C001-v2", "子", parent_case_id=root.id)
        _make_case(db, "P1-C001-v3", "子", parent_case_id=root.id)
        node = _to_node(root)
        _build_descendant_tree(db, node)
        assert len(node.children) == 2


class TestCheckChainWarning:
    def test_below_threshold(self):
        with patch("app.services.config_service.get_config", return_value="3"):
            assert _check_chain_warning(2) is None

    def test_at_threshold(self):
        with patch("app.services.config_service.get_config", return_value="3"):
            result = _check_chain_warning(3)
            assert result is not None
            assert "3" in result

    def test_above_threshold(self):
        with patch("app.services.config_service.get_config", return_value="3"):
            result = _check_chain_warning(5)
            assert result is not None
            assert "5" in result

    def test_config_exception_uses_default(self):
        with patch("app.services.config_service.get_config", side_effect=Exception("err")):
            result = _check_chain_warning(3)
            assert result is not None


class TestLineageNode:
    def test_to_node(self, db):
        case = _make_case(
            db, "P1-C001", "测试用例",
            lifecycle_status="active", prior_score=85.0, posterior_score=90.0,
        )
        node = _to_node(case)
        assert node.id == case.id
        assert node.case_no == "P1-C001"
        assert node.title == "测试用例"
        assert node.lifecycle_status == "active"
        assert node.prior_quality_score == 85.0
        assert node.posterior_quality_score == 90.0
        assert node.children == []

    def test_lineage_result_serialization(self, db):
        root = _make_case(db, "P1-C001", "根用例")
        result = get_lineage(db, root.id)
        data = result.model_dump()
        assert "root" in data
        assert "ancestors" in data
        assert "chain_length" in data
        assert "warning" in data
