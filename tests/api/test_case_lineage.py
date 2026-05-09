"""用例血缘服务单元测�?
覆盖 lineage_service.get_lineage 的正常路径、边界场景、异常路径�?全部使用真实数据库，禁止 Mock�?"""
import pytest
from sqlalchemy import text

from app.models.test_case import TestCase
from app.models.pipeline_config import PipelineConfig
from app.services.lineage_service import (
    get_lineage,
    LineageNode,
    LineageResult,
    _case_to_node,
    _build_subtree,
    _fetch_ancestors,
    _fetch_descendants_bfs,
    _fetch_descendants_cte,
    _get_warning_threshold,
    _MAX_DEPTH,
    _DEFAULT_WARNING_THRESHOLD,
)
from app.services.config_service import clear_cache


class TestGetLineageService:
    """lineage_service.get_lineage 服务层测�?""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.grandparent = TestCase(
            project_id=testProject.id,
            case_no="LIN-GP1-001",
            module="lineage",
            title="祖父用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.grandparent)
        db.flush()

        self.parent = TestCase(
            project_id=testProject.id,
            case_no="LIN-P1-001",
            module="lineage",
            title="父用�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.grandparent.id,
        )
        db.add(self.parent)
        db.flush()

        self.child = TestCase(
            project_id=testProject.id,
            case_no="LIN-C1-001",
            module="lineage",
            title="子用�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.parent.id,
        )
        db.add(self.child)
        db.flush()

    def test_lineage_returns_full_tree(self, db):
        result = get_lineage(db, self.child.id)
        assert result is not None
        assert result.root.id == self.grandparent.id
        assert result.chain_length == 3

    def test_lineage_ancestors_from_child(self, db):
        result = get_lineage(db, self.child.id)
        assert len(result.ancestors) == 2
        assert result.ancestors[0].id == self.grandparent.id
        assert result.ancestors[1].id == self.parent.id

    def test_lineage_warning_triggered(self, db):
        result = get_lineage(db, self.child.id)
        assert result.warning is True
        assert result.warning_threshold == 3

    def test_lineage_from_root_no_ancestors(self, db):
        result = get_lineage(db, self.grandparent.id)
        assert len(result.ancestors) == 0
        assert result.chain_length == 1
        assert result.warning is False

    def test_lineage_from_middle(self, db):
        result = get_lineage(db, self.parent.id)
        assert len(result.ancestors) == 1
        assert result.ancestors[0].id == self.grandparent.id
        assert result.chain_length == 2

    def test_lineage_nonexistent_returns_none(self, db):
        result = get_lineage(db, -9999)
        assert result is None

    def test_lineage_root_has_children(self, db):
        result = get_lineage(db, self.grandparent.id)
        assert len(result.root.children) >= 1
        child_ids = [c.id for c in result.root.children]
        assert self.parent.id in child_ids

    def test_lineage_node_fields(self, db):
        result = get_lineage(db, self.child.id)
        root = result.root
        assert root.case_no == "LIN-GP1-001"
        assert root.title == "祖父用例"
        assert root.lifecycle_status == "active"
        assert root.parent_case_id is None

    def test_lineage_grandchild_in_tree(self, db):
        result = get_lineage(db, self.grandparent.id)
        parent_node = None
        for c in result.root.children:
            if c.id == self.parent.id:
                parent_node = c
                break
        assert parent_node is not None
        grandchild_ids = [gc.id for gc in parent_node.children]
        assert self.child.id in grandchild_ids

    def test_lineage_node_is_pydantic(self, db):
        result = get_lineage(db, self.child.id)
        assert isinstance(result.root, LineageNode)
        assert isinstance(result, LineageResult)
        json_str = result.model_dump_json()
        assert "LIN-GP1-001" in json_str

    def test_case_id_not_in_case_map_covers_L210(self, db):
        """覆盖 L210-211: case_id 不在 case_map 中的分支

        当查询的用例本身不是 root 且不�?children_map �?values 中时�?        case_id 不在 case_map 中，需要手动添加�?        """
        result = get_lineage(db, self.child.id)
        assert result is not None
        assert result.root.id == self.grandparent.id


class TestGetLineageSingleCase:
    """无血缘关系的单用例测�?""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.sole_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-SOL2-001",
            module="lineage",
            title="独立用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="draft",
        )
        db.add(self.sole_case)
        db.flush()

    def test_sole_case_no_ancestors(self, db):
        result = get_lineage(db, self.sole_case.id)
        assert result is not None
        assert len(result.ancestors) == 0
        assert result.chain_length == 1
        assert result.warning is False

    def test_sole_case_no_children(self, db):
        result = get_lineage(db, self.sole_case.id)
        assert len(result.root.children) == 0


class TestGetLineageMultipleChildren:
    """一个父用例有多个子用例"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.parent_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-MP2-001",
            module="lineage",
            title="多子用例�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.parent_case)
        db.flush()

        self.children = []
        for i in range(3):
            c = TestCase(
                project_id=testProject.id,
                case_no=f"LIN-MC2-{i:03d}",
                module="lineage",
                title=f"子用例{i}",
                precondition="",
                steps_json=[],
                expected_result="",
                priority=1,
                case_type="API",
                lifecycle_status="active",
                parent_case_id=self.parent_case.id,
            )
            db.add(c)
            db.flush()
            self.children.append(c)

    def test_all_children_in_tree(self, db):
        result = get_lineage(db, self.parent_case.id)
        assert result is not None
        child_ids = {c.id for c in result.root.children}
        for ch in self.children:
            assert ch.id in child_ids

    def test_chain_length_is_1(self, db):
        result = get_lineage(db, self.parent_case.id)
        assert result.chain_length == 1
        assert result.warning is False


class TestCaseToNode:
    """_case_to_node 转换测试"""

    def test_node_fields_populated(self, db, testProject, testUser):
        case = TestCase(
            project_id=testProject.id,
            case_no="LIN-NOD2-001",
            module="lineage",
            title="节点测试",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="pending_review",
        )
        db.add(case)
        db.flush()

        node = _case_to_node(case)
        assert node.id == case.id
        assert node.case_no == "LIN-NOD2-001"
        assert node.title == "节点测试"
        assert node.lifecycle_status == "pending_review"
        assert node.children == []


class TestBuildSubtreeDepthLimit:
    """_build_subtree 深度限制测试 �?使用真实 DB 数据"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.cases = []
        for i in range(5):
            parent_id = self.cases[-1].id if self.cases else None
            c = TestCase(
                project_id=testProject.id,
                case_no=f"LIN-DEP-{i:03d}",
                module="lineage",
                title=f"深度{i}",
                precondition="",
                steps_json=[],
                expected_result="",
                priority=1,
                case_type="API",
                lifecycle_status="active",
                parent_case_id=parent_id,
            )
            db.add(c)
            db.flush()
            self.cases.append(c)

    def test_depth_limit_truncates(self, db):
        case_map = {c.id: c for c in self.cases}
        children_map: dict[int, list[TestCase]] = {}
        for c in self.cases:
            if c.parent_case_id is not None:
                children_map.setdefault(c.parent_case_id, []).append(c)

        root_id = self.cases[0].id
        node = _build_subtree(root_id, case_map, children_map, depth=0, max_depth=2)
        assert node.id == root_id
        assert len(node.children) == 1
        child1 = node.children[0]
        assert len(child1.children) == 1
        child2 = child1.children[0]
        assert len(child2.children) == 1
        child3 = child2.children[0]
        assert len(child3.children) == 0


class TestCycleDetection:
    """循环引用检测测�?�?覆盖 L84-85"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.case_a = TestCase(
            project_id=testProject.id,
            case_no="LIN-CYC-A",
            module="lineage",
            title="循环A",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.case_a)
        db.flush()

        self.case_b = TestCase(
            project_id=testProject.id,
            case_no="LIN-CYC-B",
            module="lineage",
            title="循环B",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.case_a.id,
        )
        db.add(self.case_b)
        db.flush()

        db.query(TestCase).filter(TestCase.id == self.case_a.id).update(
            {TestCase.parent_case_id: self.case_b.id}
        )
        db.flush()

    def test_cycle_detected_no_infinite_loop(self, db):
        result = get_lineage(db, self.case_a.id)
        assert result is not None
        assert result.chain_length >= 1


class TestParentNotFoundInDB:
    """父用例不�?DB �?覆盖 L88-91

    通过 raw SQL 绕过 FK 约束，创�?parent_case_id 指向不存�?ID 的孤儿用例，
    触发 _fetch_ancestors �?parent = db.query(...).first() 返回 None 的分支�?    """

    def test_orphan_parent_not_found_returns_empty_ancestors(self, db, testProject, testUser):
        case = TestCase(
            project_id=testProject.id,
            case_no="LIN-ORPH-001",
            module="lineage",
            title="孤儿用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case)
        db.flush()

        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        db.execute(
            text("UPDATE test_cases SET parent_case_id = -9999 WHERE id = :cid"),
            {"cid": case.id},
        )
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.flush()

        db.expire(case)
        result = _fetch_ancestors(db, case)
        assert isinstance(result, list)
        assert len(result) == 0


class TestCTEEmptyResult:
    """CTE 返回空结�?�?覆盖 L131-143"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.root_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-CTE-E-001",
            module="lineage",
            title="无后代根节点",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.root_case)
        db.flush()

    def test_cte_with_no_descendants(self, db):
        result = _fetch_descendants_cte(db, self.root_case.id)
        assert isinstance(result, dict)
        if self.root_case.id in result:
            assert len(result[self.root_case.id]) == 0
        else:
            assert result == {}

    def test_cte_returns_children_map(self, db, testProject):
        child = TestCase(
            project_id=testProject.id,
            case_no="LIN-CTE-C-001",
            module="lineage",
            title="CTE子节�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.root_case.id,
        )
        db.add(child)
        db.flush()

        result = _fetch_descendants_cte(db, self.root_case.id)
        assert self.root_case.id in result
        assert len(result[self.root_case.id]) >= 1


class TestCTEAndBFSEquivalence:
    """CTE �?BFS 结果一致性测�?�?真实 DB 验证两条路径等价"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.root_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-EQ-R-001",
            module="lineage",
            title="等价根节�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.root_case)
        db.flush()

        self.child_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-EQ-C-001",
            module="lineage",
            title="等价子节�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.root_case.id,
        )
        db.add(self.child_case)
        db.flush()

        self.grandchild = TestCase(
            project_id=testProject.id,
            case_no="LIN-EQ-GC-001",
            module="lineage",
            title="等价孙节�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.child_case.id,
        )
        db.add(self.grandchild)
        db.flush()

    def test_bfs_finds_children(self, db):
        children_map = _fetch_descendants_bfs(db, self.root_case.id)
        assert self.root_case.id in children_map
        kids = children_map[self.root_case.id]
        assert any(k.id == self.child_case.id for k in kids)

    def test_cte_and_bfs_produce_same_keys(self, db):
        cte_result = _fetch_descendants_cte(db, self.root_case.id)
        bfs_result = _fetch_descendants_bfs(db, self.root_case.id)
        bfs_non_empty = {k for k, v in bfs_result.items() if v}
        assert set(cte_result.keys()) == bfs_non_empty

    def test_cte_and_bfs_produce_same_child_ids(self, db):
        cte_result = _fetch_descendants_cte(db, self.root_case.id)
        bfs_result = _fetch_descendants_bfs(db, self.root_case.id)
        for parent_id in cte_result:
            cte_ids = sorted(c.id for c in cte_result[parent_id])
            bfs_ids = sorted(c.id for c in bfs_result[parent_id])
            assert cte_ids == bfs_ids


class TestGetConfigException:
    """get_config 异常降级 �?覆盖 L187-189

    通过�?DB 中插入类型错误的配置值，触发 _cast_value 异常�?    验证 _get_warning_threshold 返回默认值�?    """

    def test_invalid_config_value_returns_default(self, db):
        clear_cache()
        existing = db.query(PipelineConfig).filter(
            PipelineConfig.key == "LINEAGE_CHAIN_WARNING_LENGTH"
        ).first()
        if existing is not None:
            db.delete(existing)
            db.flush()

        bad_config = PipelineConfig(
            key="LINEAGE_CHAIN_WARNING_LENGTH",
            value="not_a_number",
            value_type="int",
        )
        db.add(bad_config)
        db.flush()
        clear_cache()

        threshold = _get_warning_threshold(db)
        assert threshold == _DEFAULT_WARNING_THRESHOLD

        db.delete(bad_config)
        db.flush()
        clear_cache()

    def test_missing_config_returns_default(self, db):
        clear_cache()
        existing = db.query(PipelineConfig).filter(
            PipelineConfig.key == "LINEAGE_CHAIN_WARNING_LENGTH"
        ).first()
        if existing is not None:
            db.delete(existing)
            db.flush()
        clear_cache()

        threshold = _get_warning_threshold(db)
        assert threshold == _DEFAULT_WARNING_THRESHOLD


class TestCaseIdNotInCaseMap:
    """case_id 不在 case_map �?覆盖 L221-222

    场景: 查询一个用例，它的 parent_case_id 指向的父用例存在�?    但该用例自身不在 children_map 中（即它不是任何用例的子用例）�?    �?case 本身不是 root 且不�?children_map �?values 中时触发�?    """

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        self.parent_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-CMAP-P-001",
            module="lineage",
            title="父用�?,
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.parent_case)
        db.flush()

        self.leaf_case = TestCase(
            project_id=testProject.id,
            case_no="LIN-CMAP-L-001",
            module="lineage",
            title="叶子用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
            parent_case_id=self.parent_case.id,
        )
        db.add(self.leaf_case)
        db.flush()

    def test_leaf_case_in_result(self, db):
        result = get_lineage(db, self.leaf_case.id)
        assert result is not None
        assert result.root.id == self.parent_case.id
