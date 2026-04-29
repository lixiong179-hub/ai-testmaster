import uuid
import pytest
from app.crud.test_case_query import (
    get_test_case_by_id,
    get_test_case_by_case_no,
    get_test_cases_by_project,
    get_test_cases_by_project_and_user,
    get_test_cases_count,
    get_failed_test_cases,
)
from app.crud.test_case_mutate import (
    create_test_case,
    update_test_case,
    delete_test_case,
    batch_create_test_cases,
)
from tests.helpers import createTestTestCase, createTestProject, createTestUser


class TestCreateTestCase:
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
        assert case.precondition == "user exists in system"
        assert case.priority == 1
        assert case.case_type == "UI"
        assert case.generate_status == 0

    def test_create_test_case_with_optional_fields(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="search",
            title="search with keyword",
            precondition="none",
            steps=[{"step": 1, "action": "input keyword", "param": "test"}],
            expected_result="results displayed",
            priority=2,
            case_type="API",
            exec_script="script.py",
            generate_status=1,
        )
        assert case.exec_script == "script.py"
        assert case.generate_status == 1

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


class TestUpdateTestCase:
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

    def test_update_test_case_multiple_fields(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="old_module",
            title="old title",
            precondition="old precondition",
            steps=[],
            expected_result="old result",
            priority=3,
            case_type="manual",
        )
        updated = update_test_case(
            db=db,
            test_case_id=case.id,
            project_id=testProject.id,
            module="new_module",
            title="new title",
            precondition="new precondition",
            expected_result="new result",
            priority=1,
        )
        assert updated.module == "new_module"
        assert updated.title == "new title"
        assert updated.precondition == "new precondition"
        assert updated.expected_result == "new result"
        assert updated.priority == 1


class TestDeleteTestCase:
    def test_delete_test_case_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
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

    def test_delete_test_case_wrong_project(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
            title="to be deleted",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        result = delete_test_case(db=db, test_case_id=case.id, project_id=99999)
        assert result is False


class TestBatchCreateTestCases:
    def test_batch_create_normal(self, db, testProject):
        data = [
            {
                "case_no": f"CASE-B1-{uuid.uuid4().hex[:8]}",
                "module": "batch",
                "title": "batch case 1",
                "precondition": "none",
                "steps": [{"step": 1, "action": "do something"}],
                "expected_result": "ok",
                "priority": 1,
                "case_type": "UI",
            },
            {
                "case_no": f"CASE-B2-{uuid.uuid4().hex[:8]}",
                "module": "batch",
                "title": "batch case 2",
                "precondition": "none",
                "steps": [],
                "expected_result": "ok",
                "priority": 2,
                "case_type": "API",
            },
        ]
        cases = batch_create_test_cases(db=db, project_id=testProject.id, test_cases_data=data)
        assert len(cases) == 2
        assert cases[0].title == "batch case 1"
        assert cases[1].title == "batch case 2"
        assert all(c.project_id == testProject.id for c in cases)

    def test_batch_create_single_item(self, db, testProject):
        data = [
            {
                "case_no": f"CASE-S-{uuid.uuid4().hex[:8]}",
                "module": "single",
                "title": "single batch case",
                "precondition": "none",
                "steps": [],
                "expected_result": "ok",
                "priority": 3,
                "case_type": "manual",
            },
        ]
        cases = batch_create_test_cases(db=db, project_id=testProject.id, test_cases_data=data)
        assert len(cases) == 1

    def test_batch_create_with_optional_fields(self, db, testProject):
        data = [
            {
                "case_no": f"CASE-O-{uuid.uuid4().hex[:8]}",
                "module": "optional",
                "title": "case with optional fields",
                "precondition": "none",
                "steps": [],
                "expected_result": "ok",
                "priority": 1,
                "case_type": "UI",
                "exec_script": "run.py",
                "generate_status": 1,
            },
        ]
        cases = batch_create_test_cases(db=db, project_id=testProject.id, test_cases_data=data)
        assert cases[0].exec_script == "run.py"
        assert cases[0].generate_status == 1


class TestGetTestCaseById:
    def test_get_test_case_by_id_normal(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
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
        assert found.title == "findable case"

    def test_get_test_case_by_id_nonexistent(self, db, testProject):
        found = get_test_case_by_id(db=db, test_case_id=99999, project_id=testProject.id)
        assert found is None

    def test_get_test_case_by_id_wrong_project(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="login",
            title="project scoped case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        found = get_test_case_by_id(db=db, test_case_id=case.id, project_id=99999)
        assert found is None


class TestGetTestCaseByCaseNo:
    def test_get_test_case_by_case_no_normal(self, db, testProject):
        caseNo = f"CASE-NO-{uuid.uuid4().hex[:8]}"
        create_test_case(
            db=db,
            case_no=caseNo,
            project_id=testProject.id,
            module="login",
            title="case no lookup",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        found = get_test_case_by_case_no(db=db, case_no=caseNo)
        assert found is not None
        assert found.case_no == caseNo

    def test_get_test_case_by_case_no_nonexistent(self, db):
        found = get_test_case_by_case_no(db=db, case_no="NONEXISTENT-CASE-NO")
        assert found is None


class TestGetTestCasesByProject:
    def test_get_test_cases_by_project_normal(self, db, testProject):
        for i in range(3):
            create_test_case(
                db=db,
                case_no=f"CASE-LIST-{i}-{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                module="login",
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
            module="module_a",
            title="module a case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        create_test_case(
            db=db,
            case_no=f"CASE-MOD2-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="module_b",
            title="module b case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        cases = get_test_cases_by_project(db=db, project_id=testProject.id, module="module_a")
        assert all(c.module == "module_a" for c in cases)

    def test_get_test_cases_by_project_with_priority_filter(self, db, testProject):
        create_test_case(
            db=db,
            case_no=f"CASE-PRI1-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="priority_test",
            title="high priority case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=1,
            case_type="UI",
        )
        cases = get_test_cases_by_project(db=db, project_id=testProject.id, priority=1)
        assert all(c.priority == 1 for c in cases)

    def test_get_test_cases_by_project_with_case_type_filter(self, db, testProject):
        create_test_case(
            db=db,
            case_no=f"CASE-CT-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="type_test",
            title="api case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="API",
        )
        cases = get_test_cases_by_project(db=db, project_id=testProject.id, case_type="API")
        assert all(c.case_type == "API" for c in cases)

    def test_get_test_cases_by_project_with_generate_status_filter(self, db, testProject):
        create_test_case(
            db=db,
            case_no=f"CASE-GS-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="status_test",
            title="generated case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
            generate_status=1,
        )
        cases = get_test_cases_by_project(db=db, project_id=testProject.id, generate_status=1)
        assert all(c.generate_status == 1 for c in cases)

    def test_get_test_cases_by_project_pagination(self, db, testProject):
        for i in range(5):
            create_test_case(
                db=db,
                case_no=f"CASE-PAGE-{i}-{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                module="pagination",
                title=f"page case {i}",
                precondition="none",
                steps=[],
                expected_result="ok",
                priority=2,
                case_type="UI",
            )
        first_page = get_test_cases_by_project(db=db, project_id=testProject.id, skip=0, limit=2)
        second_page = get_test_cases_by_project(db=db, project_id=testProject.id, skip=2, limit=2)
        assert len(first_page) <= 2
        assert len(second_page) <= 2

    def test_get_test_cases_by_project_empty(self, db, testProject):
        cases = get_test_cases_by_project(db=db, project_id=99999)
        assert cases == []


class TestGetTestCasesByProjectAndUser:
    def test_get_test_cases_by_project_and_user_normal(self, db, testProject, testUser):
        create_test_case(
            db=db,
            case_no=f"CASE-PU-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="user_filter",
            title="user project case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        cases = get_test_cases_by_project_and_user(
            db=db, project_id=testProject.id, user_id=testUser.id
        )
        assert len(cases) >= 1

    def test_get_test_cases_by_project_and_user_wrong_user(self, db, testProject):
        cases = get_test_cases_by_project_and_user(
            db=db, project_id=testProject.id, user_id=99999
        )
        assert cases == []

    def test_get_test_cases_by_project_and_user_with_filters(self, db, testProject, testUser):
        create_test_case(
            db=db,
            case_no=f"CASE-PUF-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="filter_mod",
            title="filtered case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=1,
            case_type="API",
        )
        cases = get_test_cases_by_project_and_user(
            db=db,
            project_id=testProject.id,
            user_id=testUser.id,
            module="filter_mod",
            priority=1,
            case_type="API",
        )
        assert all(c.module == "filter_mod" for c in cases)


class TestGetTestCasesCount:
    def test_get_test_cases_count_normal(self, db, testProject, testUser):
        create_test_case(
            db=db,
            case_no=f"CASE-CNT-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="count_test",
            title="count case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        count = get_test_cases_count(db=db, project_id=testProject.id, user_id=testUser.id)
        assert count >= 1

    def test_get_test_cases_count_with_filters(self, db, testProject, testUser):
        create_test_case(
            db=db,
            case_no=f"CASE-CNTF-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="count_filter",
            title="count filter case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=1,
            case_type="API",
        )
        count = get_test_cases_count(
            db=db,
            project_id=testProject.id,
            user_id=testUser.id,
            module="count_filter",
            priority=1,
        )
        assert count >= 1

    def test_get_test_cases_count_wrong_user(self, db, testProject):
        count = get_test_cases_count(db=db, project_id=testProject.id, user_id=99999)
        assert count == 0


class TestGetFailedTestCases:
    def test_get_failed_test_cases_with_failures(self, db, testProject, testUser):
        create_test_case(
            db=db,
            case_no=f"CASE-FAIL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="fail_test",
            title="failed case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
            generate_status=2,
        )
        cases = get_failed_test_cases(db=db, project_id=testProject.id, user_id=testUser.id)
        assert len(cases) >= 1
        assert all(c.generate_status == 2 for c in cases)

    def test_get_failed_test_cases_no_failures(self, db, testProject, testUser):
        create_test_case(
            db=db,
            case_no=f"CASE-OK-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="ok_test",
            title="successful case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
            generate_status=1,
        )
        before_count = len(get_failed_test_cases(db=db, project_id=testProject.id, user_id=testUser.id))
        only_status_2 = [c for c in get_failed_test_cases(db=db, project_id=testProject.id, user_id=testUser.id)]
        for c in only_status_2:
            assert c.generate_status == 2

    def test_get_failed_test_cases_wrong_user(self, db, testProject):
        cases = get_failed_test_cases(db=db, project_id=testProject.id, user_id=99999)
        assert cases == []
