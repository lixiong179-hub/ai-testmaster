import uuid
import pytest
from app.crud.test_case_query import (
    get_test_case_by_id,
    get_test_cases_by_project,
    get_test_cases_count,
)
from app.crud.test_case_mutate import (
    create_test_case,
    update_test_case,
    delete_test_case,
)
from app.crud.test_point import (
    create_test_point,
    get_test_point_by_id,
    get_test_points_by_project,
    update_test_point,
    delete_test_point,
)
from app.crud.project import (
    create_project,
    get_projects,
    get_project_by_id,
    delete_project,
)
from app.schemas.test_case import TestCaseCreate, TestCaseUpdate
from app.schemas.project import ProjectCreate


class TestTestCaseCRUD:
    def test_create_test_case_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
            title="verify login with valid credentials",
            precondition="user exists in system",
            steps=[{"step": 1, "action": "input username", "param": "admin"}],
            expected_result="login successful",
            priority=1,
            case_type="UI",
        )
        assert case is not None
        assert case.id is not None
        assert case.project_id == testProject.id
        assert case.module == "login"
        assert case.title == "verify login with valid credentials"
        assert case.priority == 1

    def test_create_test_case_empty_steps(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="search",
            title="search with keyword",
            precondition="none",
            steps=[],
            expected_result="results displayed",
            priority=2,
            case_type="API",
        )
        assert case is not None
        assert len(case.steps_json) == 0

    def test_create_test_case_boundary_priority(self, db, testProject):
        for priority in [1, 2, 3]:
            case = create_test_case(
                db=db,
                case_no=f"CASE-P{priority}-{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                module="boundary",
                title=f"priority {priority} case",
                precondition="none",
                steps=[],
                expected_result="ok",
                priority=priority,
                case_type="manual",
            )
            assert case.priority == priority

    def test_create_test_case_null_precondition(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="null_precond",
            title="case with null precondition",
            precondition="",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        assert case.precondition == ""

    def test_get_test_case_by_id_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="getbyid",
            title="findable case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        found = get_test_case_by_id(db=db, test_case_id=case.id, project_id=testProject.id)
        assert found is not None
        assert found.id == case.id

    def test_get_test_case_by_id_nonexistent(self, db, testProject):
        found = get_test_case_by_id(db=db, test_case_id=99999, project_id=testProject.id)
        assert found is None

    def test_get_test_cases_by_project_normal(self, db, testProject):
        for i in range(3):
            create_test_case(
                db=db,
                case_no=f"CASE-LIST-{i}-{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                module="list_mod",
                title=f"list case {i}",
                precondition="none",
                steps=[],
                expected_result="ok",
                priority=2,
                case_type="UI",
            )
        cases = get_test_cases_by_project(db=db, project_id=testProject.id)
        assert len(cases) >= 3

    def test_get_test_cases_by_project_with_module_filter(self, db, testProject):
        create_test_case(
            db=db,
            case_no=f"CASE-MOD1-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="filter_module",
            title="module filter case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        cases = get_test_cases_by_project(db=db, project_id=testProject.id, module="filter_module")
        assert all(c.module == "filter_module" for c in cases)

    def test_update_test_case_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
            title="original title",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        updated = update_test_case(
            db=db,
            test_case_id=case.id,
            project_id=testProject.id,
            title="updated title",
            priority=1,
        )
        assert updated is not None
        assert updated.title == "updated title"
        assert updated.priority == 1

    def test_update_test_case_nonexistent(self, db, testProject):
        result = update_test_case(
            db=db,
            test_case_id=99999,
            project_id=testProject.id,
            title="should not update",
        )
        assert result is None

    def test_update_test_case_wrong_project(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
            title="original",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        result = update_test_case(
            db=db,
            test_case_id=case.id,
            project_id=99999,
            title="should not update",
        )
        assert result is None

    def test_delete_test_case_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="delete_mod",
            title="to be deleted",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        result = delete_test_case(db=db, test_case_id=case.id, project_id=testProject.id)
        assert result is True
        found = get_test_case_by_id(db=db, test_case_id=case.id, project_id=testProject.id)
        assert found is None

    def test_delete_test_case_nonexistent(self, db, testProject):
        result = delete_test_case(db=db, test_case_id=99999, project_id=testProject.id)
        assert result is False


class TestTestPointCRUD:
    def test_create_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="password login",
            point="valid credentials login",
            priority=1,
        )
        assert point is not None
        assert point.id is not None
        assert point.project_id == testProject.id
        assert point.module == "login"
        assert point.priority == 1

    def test_create_test_point_with_ai_prompt(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="search",
            function="keyword search",
            point="search with special chars",
            priority=2,
            ai_prompt="focus on XSS scenarios",
        )
        assert point.ai_prompt == "focus on XSS scenarios"

    def test_create_test_point_without_ai_prompt(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="logout",
            function="session logout",
            point="logout clears session",
            priority=3,
        )
        assert point.ai_prompt is None

    def test_create_test_point_boundary_priority(self, db, testProject):
        for p in [1, 2, 3]:
            point = create_test_point(
                db=db,
                project_id=testProject.id,
                module="boundary",
                function=f"priority {p}",
                point=f"priority {p} test",
                priority=p,
            )
            assert point.priority == p

    def test_get_test_point_by_id_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="getbyid",
            function="login check",
            point="valid login",
            priority=1,
        )
        found = get_test_point_by_id(db=db, test_point_id=point.id, project_id=testProject.id)
        assert found is not None
        assert found.id == point.id

    def test_get_test_point_by_id_nonexistent(self, db, testProject):
        found = get_test_point_by_id(db=db, test_point_id=99999, project_id=testProject.id)
        assert found is None

    def test_get_test_points_by_project_normal(self, db, testProject):
        for i in range(3):
            create_test_point(
                db=db,
                project_id=testProject.id,
                module="list_mod",
                function=f"func_{i}",
                point=f"point_{i}",
                priority=2,
            )
        points = get_test_points_by_project(db=db, project_id=testProject.id)
        assert len(points) >= 3

    def test_get_test_points_by_project_with_priority_filter(self, db, testProject):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="pri_filter",
            function="high pri",
            point="high priority point",
            priority=1,
        )
        points = get_test_points_by_project(db=db, project_id=testProject.id, priority=1)
        assert all(p.priority == 1 for p in points)

    def test_update_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="update_mod",
            function="login check",
            point="original point",
            priority=2,
        )
        updated = update_test_point(
            db=db,
            test_point_id=point.id,
            project_id=testProject.id,
            point="updated point",
            priority=1,
        )
        assert updated is not None
        assert updated.point == "updated point"
        assert updated.priority == 1

    def test_update_test_point_nonexistent(self, db, testProject):
        result = update_test_point(
            db=db, test_point_id=99999, project_id=testProject.id, point="should not update"
        )
        assert result is None

    def test_delete_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="delete_mod",
            function="login check",
            point="to be deleted",
            priority=2,
        )
        result = delete_test_point(db=db, test_point_id=point.id, project_id=testProject.id)
        assert result is True
        found = get_test_point_by_id(db=db, test_point_id=point.id, project_id=testProject.id)
        assert found is None

    def test_delete_test_point_nonexistent(self, db, testProject):
        result = delete_test_point(db=db, test_point_id=99999, project_id=testProject.id)
        assert result is False


class TestElementLocatorCRUD:
    def test_create_locator_with_css(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-LOC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="locator",
            title="locator test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click button",
            expected_result="button clicked",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="login button",
            element_type="button",
            css_selector="#login-btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.id is not None
        assert locator.css_selector == "#login-btn"

    def test_create_locator_with_xpath(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-XPATH-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="xpath",
            title="xpath test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click link",
            expected_result="link clicked",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="navigation link",
            element_type="link",
            xpath="//a[@class='nav-link']",
            source="ai",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.xpath == "//a[@class='nav-link']"

    def test_create_locator_with_ai_coordinate(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AICOORD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="aicoord",
            title="ai coordinate test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click area",
            expected_result="area clicked",
        )
        db.add(step)
        db.flush()
        coordinate = {"x": 100, "y": 200, "width": 50, "height": 30}
        locator = ElementLocator(
            step_id=step.id,
            element_description="clickable area",
            element_type="button",
            ai_coordinate=coordinate,
            ai_confidence=0.95,
            source="ai",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.ai_coordinate == coordinate
        assert locator.ai_confidence == 0.95

    def test_locator_record_success(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-SUCC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="success",
            title="record success test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        db.commit()
        db.refresh(locator)
        assert locator.success_count == 1
        assert locator.version == 1

    def test_locator_record_failure(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-FAIL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="failure",
            title="record failure test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_failure()
        db.commit()
        db.refresh(locator)
        assert locator.fail_count == 1

    def test_locator_success_rate_calculation(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-RATE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="rate",
            title="success rate test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        locator.record_failure()
        db.commit()
        db.refresh(locator)
        assert locator.success_rate == 0.5

    def test_locator_priority_order(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-PRI-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="priority",
            title="priority order test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        from app.models.element_locator import ElementLocator
        from app.models.test_case import TestStep
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            xpath="//button",
            element_id="submit",
            element_name="action",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        order = locator.priority_order
        assert "css" in order
        assert "xpath" in order
        assert "id" in order
        assert "name" in order
        assert order[0] == "css"


class TestProjectCRUD:
    def test_create_project_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_project_{uuid.uuid4().hex[:8]}",
            description="crud test project",
            project_type="web",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project is not None
        assert project.id is not None
        assert project.name == projectCreate.name
        assert project.user_id == testUser.id
        assert project.status == 1

    def test_create_project_app_type(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_app_{uuid.uuid4().hex[:8]}",
            description="app type project",
            project_type="app",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project.project_type == "app"

    def test_create_project_minimal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_min_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project is not None
        assert project.description is None

    def test_create_project_default_type(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_default_type_{uuid.uuid4().hex[:8]}",
            description="default type",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project.project_type == "web"

    def test_create_project_long_description(self, db, testUser):
        longDesc = "A" * 500
        projectCreate = ProjectCreate(
            name=f"crud_longdesc_{uuid.uuid4().hex[:8]}",
            description=longDesc,
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project.description == longDesc

    def test_get_projects_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_list_{uuid.uuid4().hex[:8]}",
            description="list test",
        )
        create_project(db=db, project=projectCreate, user_id=testUser.id)
        projects = get_projects(db=db, user_id=testUser.id)
        assert len(projects) >= 1

    def test_get_projects_pagination(self, db, testUser):
        for i in range(3):
            projectCreate = ProjectCreate(
                name=f"crud_page_{i}_{uuid.uuid4().hex[:8]}",
            )
            create_project(db=db, project=projectCreate, user_id=testUser.id)
        first = get_projects(db=db, user_id=testUser.id, skip=0, limit=2)
        assert len(first) <= 2

    def test_get_projects_wrong_user(self, db, testUser):
        projects = get_projects(db=db, user_id=99999)
        found_test_user = [p for p in projects if p.user_id == testUser.id]
        assert len(found_test_user) == 0

    def test_get_project_by_id_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_get_{uuid.uuid4().hex[:8]}",
            description="get by id test",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        found = get_project_by_id(db=db, project_id=project.id, user_id=testUser.id)
        assert found is not None
        assert found.id == project.id

    def test_get_project_by_id_nonexistent(self, db, testUser):
        found = get_project_by_id(db=db, project_id=99999, user_id=testUser.id)
        assert found is None

    def test_get_project_by_id_zero_id(self, db, testUser):
        found = get_project_by_id(db=db, project_id=0, user_id=testUser.id)
        assert found is None

    def test_delete_project_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_del_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        result = delete_project(db=db, project_id=project.id, user_id=testUser.id)
        assert result is True
        found = get_project_by_id(db=db, project_id=project.id, user_id=testUser.id)
        assert found is None

    def test_delete_project_nonexistent(self, db, testUser):
        result = delete_project(db=db, project_id=99999, user_id=testUser.id)
        assert result is False

    def test_delete_project_wrong_user(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_wrong_del_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        result = delete_project(db=db, project_id=project.id, user_id=99999)
        assert result is False
