import pytest
from app.schemas.test_case import (
    TestCaseStep,
    TestCaseBase,
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseGenerateRequest,
    TestCaseListRequest,
    TestCaseListResponse,
    TestCaseRetryRequest,
    TestCaseDeleteRequest,
)
from app.schemas.test_case._flow import (
    FlowMetaSchema,
    FlowNodeSchema,
    FlowEdgeSchema,
    FlowSortDataSchema,
)
from app.schemas.test_case._precondition import (
    PreconditionStepCreate,
    PreconditionStepUpdate,
    PreconditionStepBatchSave,
)


class TestTestCaseStep:
    def test_normal(self):
        step = TestCaseStep(step=1, action="点击登录", param="", expected_result="登录成功")
        assert step.step == 1
        assert step.action == "点击登录"
        assert step.expected_result == "登录成功"

    def test_with_optional_fields(self):
        step = TestCaseStep(
            step="1",
            action="输入",
            param="用户名",
            action_type="input",
            input_value="admin",
            target_element="用户名输入框",
            ui_elements=["用户名输入框"],
        )
        assert step.action_type == "input"
        assert step.input_value == "admin"
        assert step.target_element == "用户名输入框"

    def test_extra_fields_allowed(self):
        step = TestCaseStep(step=1, action="A", custom_field="custom")
        assert step.model_extra is not None


class TestTestCaseBase:
    def test_normal(self):
        case = TestCaseBase(title="登录验证")
        assert case.title == "登录验证"
        assert case.priority == 2
        assert case.lifecycle_status == "draft"
        assert case.steps == []

    def test_title_strip(self):
        case = TestCaseBase(title="  验证  ")
        assert case.title == "验证"

    def test_priority_range(self):
        case = TestCaseBase(title="T", priority=1)
        assert case.priority == 1
        case = TestCaseBase(title="T", priority=3)
        assert case.priority == 3

    def test_invalid_priority(self):
        with pytest.raises(Exception):
            TestCaseBase(title="T", priority=0)
        with pytest.raises(Exception):
            TestCaseBase(title="T", priority=4)

    def test_empty_title_rejected(self):
        with pytest.raises(Exception):
            TestCaseBase(title="")

    def test_lifecycle_status_validation(self):
        case = TestCaseBase(title="T", lifecycle_status="active")
        assert case.lifecycle_status == "active"
        with pytest.raises(Exception):
            TestCaseBase(title="T", lifecycle_status="invalid_status")


class TestTestCaseCreate:
    def test_normal(self):
        case = TestCaseCreate(project_id=1, title="创建用例")
        assert case.project_id == 1
        assert case.title == "创建用例"

    def test_with_optional_fields(self):
        case = TestCaseCreate(
            project_id=1,
            title="T",
            test_point_id=10,
            ai_change_type="added",
            test_data={"normal": {"key": "val"}},
        )
        assert case.test_point_id == 10
        assert case.ai_change_type == "added"

    def test_missing_project_id(self):
        with pytest.raises(Exception):
            TestCaseCreate(title="T")


class TestTestCaseUpdate:
    def test_all_optional(self):
        update = TestCaseUpdate()
        assert update.title is None
        assert update.module is None

    def test_partial_update(self):
        update = TestCaseUpdate(title="新标题", priority=1)
        assert update.title == "新标题"
        assert update.priority == 1


class TestTestCaseGenerateRequest:
    def test_normal(self):
        req = TestCaseGenerateRequest(project_id=1)
        assert req.project_id == 1
        assert req.point_ids is None

    def test_with_point_ids(self):
        req = TestCaseGenerateRequest(project_id=1, point_ids=[1, 2, 3])
        assert len(req.point_ids) == 3


class TestTestCaseListRequest:
    def test_defaults(self):
        req = TestCaseListRequest(project_id=1)
        assert req.page == 1
        assert req.page_size == 10

    def test_pagination_validation(self):
        with pytest.raises(Exception):
            TestCaseListRequest(project_id=1, page=0)
        with pytest.raises(Exception):
            TestCaseListRequest(project_id=1, page_size=101)


class TestTestCaseRetryRequest:
    def test_normal(self):
        req = TestCaseRetryRequest(project_id=1)
        assert req.project_id == 1


class TestTestCaseDeleteRequest:
    def test_normal(self):
        req = TestCaseDeleteRequest(project_id=1)
        assert req.project_id == 1


class TestFlowSchemas:
    def test_flow_meta(self):
        meta = FlowMetaSchema(parent_node_id="p1", trigger_condition="条件")
        assert meta.parent_node_id == "p1"

    def test_flow_node(self):
        node = FlowNodeSchema(screen_id=1, screen_order=1, flow_type="main", screen_name="开始")
        assert node.screen_id == 1

    def test_flow_edge(self):
        edge = FlowEdgeSchema(source="1", target="2", edge_type="normal", label="正常")
        assert edge.source == "1"

    def test_flow_sort_data(self):
        data = FlowSortDataSchema(
            nodes=[FlowNodeSchema(screen_id=1, screen_order=1, flow_type="main", screen_name="S")],
            edges=[FlowEdgeSchema(source="1", target="2", edge_type="normal", label="正常")],
        )
        assert len(data.nodes) == 1


class TestPreconditionStepSchemas:
    def test_create(self):
        step = PreconditionStepCreate(
            step_number=1, action="打开页面", expected_result="页面加载完成",
        )
        assert step.step_number == 1

    def test_update(self):
        step = PreconditionStepUpdate(action="新操作")
        assert step.action == "新操作"

    def test_batch_save(self):
        batch = PreconditionStepBatchSave(
            steps=[PreconditionStepCreate(step_number=1, action="A", expected_result="R")],
        )
        assert len(batch.steps) == 1
