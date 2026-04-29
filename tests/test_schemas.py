import pytest
from pydantic import ValidationError
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseListRequest,
    TestCaseStep,
)
from app.schemas.test_point import (
    TestPointCreate,
    TestPointUpdate,
)
from app.schemas.project import (
    ProjectCreate,
)


class TestTestCaseSchemas:
    def test_test_case_create_normal(self):
        case = TestCaseCreate(
            project_id=1,
            title="test case title",
            module="login",
            precondition="user exists",
            steps=[],
            expected_result="login success",
            priority=1,
            case_type="UI",
        )
        assert case.project_id == 1
        assert case.title == "test case title"
        assert case.module == "login"
        assert case.priority == 1

    def test_test_case_create_minimal(self):
        case = TestCaseCreate(
            project_id=1,
            title="minimal case",
        )
        assert case.project_id == 1
        assert case.title == "minimal case"
        assert case.module == ""
        assert case.priority == 2

    def test_test_case_create_with_steps(self):
        steps = [
            TestCaseStep(step=1, action="input username", param="admin"),
            TestCaseStep(step=2, action="input password", param="123456"),
        ]
        case = TestCaseCreate(
            project_id=1,
            title="case with steps",
            steps=steps,
        )
        assert len(case.steps) == 2
        assert case.steps[0].action == "input username"
        assert case.steps[1].param == "123456"

    def test_test_case_create_boundary_priority(self):
        for priority in [1, 2, 3]:
            case = TestCaseCreate(
                project_id=1,
                title=f"priority {priority}",
                priority=priority,
            )
            assert case.priority == priority

    def test_test_case_create_invalid_priority_low(self):
        with pytest.raises(ValidationError):
            TestCaseCreate(
                project_id=1,
                title="invalid priority",
                priority=0,
            )

    def test_test_case_create_invalid_priority_high(self):
        with pytest.raises(ValidationError):
            TestCaseCreate(
                project_id=1,
                title="invalid priority",
                priority=4,
            )

    def test_test_case_create_empty_title(self):
        with pytest.raises(ValidationError):
            TestCaseCreate(
                project_id=1,
                title="",
            )

    def test_test_case_create_missing_project_id(self):
        with pytest.raises(ValidationError):
            TestCaseCreate(
                title="no project id",
            )

    def test_test_case_create_with_test_data(self):
        steps = [
            TestCaseStep(
                step=1,
                action="input username",
                param="admin",
                test_data={"field_name": "username", "data_value": "testuser"},
            ),
        ]
        case = TestCaseCreate(
            project_id=1,
            title="case with test data",
            steps=steps,
        )
        assert case.steps[0].test_data is not None
        assert case.steps[0].test_data["field_name"] == "username"

    def test_test_case_create_case_type_validation(self):
        case = TestCaseCreate(
            project_id=1,
            title="api case",
            case_type="api_automation",
        )
        assert case.case_type == "api_automation"

    def test_test_case_update_normal(self):
        update = TestCaseUpdate(
            title="updated title",
            priority=1,
        )
        assert update.title == "updated title"
        assert update.priority == 1

    def test_test_case_update_partial(self):
        update = TestCaseUpdate(title="only title updated")
        assert update.title == "only title updated"
        assert update.module is None

    def test_test_case_update_empty(self):
        update = TestCaseUpdate()
        assert update.title is None

    def test_test_case_update_invalid_priority(self):
        with pytest.raises(ValidationError):
            TestCaseUpdate(priority=5)

    def test_test_case_list_query_normal(self):
        query = TestCaseListRequest(
            project_id=1,
            page=1,
            page_size=10,
        )
        assert query.project_id == 1
        assert query.page == 1
        assert query.page_size == 10

    def test_test_case_list_query_with_filters(self):
        query = TestCaseListRequest(
            project_id=1,
            module="login",
            priority=1,
            case_type="UI",
            generate_status=1,
        )
        assert query.module == "login"
        assert query.priority == 1
        assert query.case_type == "UI"
        assert query.generate_status == 1

    def test_test_case_list_query_pagination_boundary(self):
        query_min = TestCaseListRequest(project_id=1, page=1, page_size=1)
        assert query_min.page_size == 1

        query_max = TestCaseListRequest(project_id=1, page=1, page_size=100)
        assert query_max.page_size == 100

    def test_test_case_list_query_invalid_page_size(self):
        with pytest.raises(ValidationError):
            TestCaseListRequest(project_id=1, page=1, page_size=101)


class TestTestPointSchemas:
    def test_test_point_create_normal(self):
        point = TestPointCreate(
            project_id=1,
            module="login",
            function="password login",
            point="valid credentials login",
            priority=1,
        )
        assert point.project_id == 1
        assert point.module == "login"
        assert point.function == "password login"
        assert point.priority == 1

    def test_test_point_create_with_ai_prompt(self):
        point = TestPointCreate(
            project_id=1,
            module="search",
            function="keyword search",
            point="search functionality",
            priority=2,
            ai_prompt="focus on XSS scenarios",
        )
        assert point.ai_prompt == "focus on XSS scenarios"

    def test_test_point_create_boundary_priority(self):
        for priority in [1, 2, 3]:
            point = TestPointCreate(
                project_id=1,
                module="test",
                function="test func",
                point="test point",
                priority=priority,
            )
            assert point.priority == priority

    def test_test_point_create_invalid_priority_low(self):
        with pytest.raises(ValidationError):
            TestPointCreate(
                project_id=1,
                module="test",
                function="test func",
                point="test point",
                priority=0,
            )

    def test_test_point_create_invalid_priority_high(self):
        with pytest.raises(ValidationError):
            TestPointCreate(
                project_id=1,
                module="test",
                function="test func",
                point="test point",
                priority=4,
            )

    def test_test_point_create_missing_module(self):
        with pytest.raises(ValidationError):
            TestPointCreate(
                project_id=1,
                function="test func",
                point="test point",
                priority=1,
            )

    def test_test_point_create_empty_function(self):
        with pytest.raises(ValidationError):
            TestPointCreate(
                project_id=1,
                module="test",
                function="",
                point="test point",
                priority=1,
            )

    def test_test_point_update_normal(self):
        update = TestPointUpdate(
            module="updated module",
            priority=1,
        )
        assert update.module == "updated module"
        assert update.priority == 1

    def test_test_point_update_partial(self):
        update = TestPointUpdate(point="updated point only")
        assert update.point == "updated point only"
        assert update.module is None

    def test_test_point_update_empty(self):
        update = TestPointUpdate()
        assert update.module is None
        assert update.function is None

    def test_test_point_update_invalid_priority(self):
        with pytest.raises(ValidationError):
            TestPointUpdate(priority=5)


class TestProjectSchemas:
    def test_project_create_normal(self):
        project = ProjectCreate(
            name="test project",
            description="test description",
            project_type="web",
        )
        assert project.name == "test project"
        assert project.description == "test description"
        assert project.project_type == "web"

    def test_project_create_minimal(self):
        project = ProjectCreate(name="minimal project")
        assert project.name == "minimal project"
        assert project.description is None
        assert project.project_type == "web"

    def test_project_create_app_type(self):
        project = ProjectCreate(
            name="app project",
            project_type="app",
        )
        assert project.project_type == "app"

    def test_project_create_empty_name(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="")

    def test_project_create_long_name(self):
        long_name = "A" * 256
        with pytest.raises(ValidationError):
            ProjectCreate(name=long_name)

    def test_project_create_long_description(self):
        long_desc = "A" * 1000
        project = ProjectCreate(
            name="long desc project",
            description=long_desc,
        )
        assert len(project.description) == 1000


class TestUISpecSchemas:
    def test_technical_locator_info_normal(self):
        from app.schemas.test_case import TechnicalLocatorInfo
        locator = TechnicalLocatorInfo(
            css_selector="#login-btn",
            xpath="//button[@id='login']",
            element_type="button",
            locator_type="css",
            locator_value="#login-btn",
        )
        assert locator.css_selector == "#login-btn"
        assert locator.xpath == "//button[@id='login']"
        assert locator.element_type == "button"

    def test_technical_locator_info_with_ai_coordinate(self):
        from app.schemas.test_case import TechnicalLocatorInfo
        locator = TechnicalLocatorInfo(
            element_type="button",
            ai_coordinate={"x": 100, "y": 200, "width": 50, "height": 30},
            confidence=0.95,
            locator_type="ai",
        )
        assert locator.ai_coordinate["x"] == 100
        assert locator.confidence == 0.95

    def test_technical_step_view_normal(self):
        from app.schemas.test_case import TechnicalStepView
        step = TechnicalStepView(
            step_number=1,
            action="click button",
            expected_result="button clicked",
            has_locator=True,
            locator_status="recorded",
        )
        assert step.step_number == 1
        assert step.has_locator is True
        assert step.locator_status == "recorded"

    def test_technical_step_view_without_locator(self):
        from app.schemas.test_case import TechnicalStepView
        step = TechnicalStepView(
            step_number=1,
            action="wait",
            expected_result="wait complete",
            has_locator=False,
            locator_status="pending",
        )
        assert step.has_locator is False
        assert step.locator is None

    def test_execution_history_item_normal(self):
        from datetime import datetime
        from app.schemas.test_case import ExecutionHistoryItem
        history = ExecutionHistoryItem(
            execution_id=1,
            execution_time=datetime.now(),
            status="success",
            duration=10.5,
        )
        assert history.execution_id == 1
        assert history.status == "success"
        assert history.duration == 10.5

    def test_precondition_step_create_normal(self):
        from app.schemas.test_case import PreconditionStepCreate
        step = PreconditionStepCreate(
            step_number=1,
            action="login as admin",
            expected_result="login success",
            action_type="input",
            input_value="admin",
        )
        assert step.step_number == 1
        assert step.action == "login as admin"
        assert step.input_value == "admin"

    def test_precondition_step_update_partial(self):
        from app.schemas.test_case import PreconditionStepUpdate
        update = PreconditionStepUpdate(
            action="updated action",
        )
        assert update.action == "updated action"
        assert update.expected_result is None

    def test_precondition_step_batch_save_normal(self):
        from app.schemas.test_case import PreconditionStepBatchSave, PreconditionStepCreate
        batch = PreconditionStepBatchSave(
            steps=[
                PreconditionStepCreate(step_number=1, action="step 1"),
                PreconditionStepCreate(step_number=2, action="step 2"),
            ]
        )
        assert len(batch.steps) == 2
