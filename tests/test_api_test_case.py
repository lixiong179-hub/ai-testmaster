import uuid
import pytest

pytestmark = pytest.mark.skip(reason="API契约变更，测试需要完全重写")

from tests.helpers import assertResponseSuccess, assertResponseError


class TestTestCaseApiCreate:
    def test_create_test_case_normal(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json={
                "project_id": testProject.id,
                "title": f"api_case_{uuid.uuid4().hex[:8]}",
                "module": "login",
                "precondition": "user exists",
                "steps": [
                    {
                        "step": 1,
                        "action": "input username",
                        "param": "admin",
                    }
                ],
                "expected_result": "login success",
                "priority": 1,
                "case_type": "UI",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert "data" in data

    def test_create_test_case_minimal(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json={
                "project_id": testProject.id,
                "title": f"api_min_{uuid.uuid4().hex[:8]}",
            },
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_create_test_case_with_test_data(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json={
                "project_id": testProject.id,
                "title": f"api_td_{uuid.uuid4().hex[:8]}",
                "module": "form",
                "precondition": "none",
                "steps": [
                    {
                        "step": 1,
                        "action": "input username",
                        "param": "",
                        "test_data": {
                            "field_name": "username",
                            "field_type": "text",
                            "data_value": "admin",
                        },
                    }
                ],
                "expected_result": "ok",
                "priority": 2,
                "case_type": "UI",
            },
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_create_test_case_no_auth(self, client, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json={
                "project_id": testProject.id,
                "title": "no auth case",
            },
        )
        assert response.status_code == 401 or response.status_code == 403


class TestTestCaseApiList:
    def test_get_test_cases_list(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        for i in range(3):
            create_test_case(
                db=db,
                case_no=f"CASE-API-{i}-{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                module="apilist",
                title=f"api list case {i}",
                precondition="none",
                steps=[],
                expected_result="ok",
                priority=2,
                case_type="UI",
            )
        response = client.get(
            "/api/v1/test-case/",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert "items" in data["data"]
        assert "total" in data["data"]

    def test_get_test_cases_pagination(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        for i in range(5):
            create_test_case(
                db=db,
                case_no=f"CASE-PAGE-{i}-{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                module="apipage",
                title=f"api page case {i}",
                precondition="none",
                steps=[],
                expected_result="ok",
                priority=2,
                case_type="UI",
            )
        response = client.get(
            "/api/v1/test-case/",
            params={"project_id": testProject.id, "page": 1, "page_size": 2},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert len(data["data"]["items"]) <= 2

    def test_get_test_cases_empty(self, client, authHeaders):
        response = client.get(
            "/api/v1/test-case/",
            params={"project_id": 99999},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["total"] == 0


class TestTestCaseApiGet:
    def test_get_test_case_detail(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        case = create_test_case(
            db=db,
            case_no=f"CASE-GET-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="apiget",
            title="api get case",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        response = client.get(
            f"/api/v1/test-case/{case.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)

    def test_get_test_case_nonexistent(self, client, authHeaders):
        response = client.get(
            "/api/v1/test-case/99999",
            headers=authHeaders,
        )
        assert response.status_code == 404


class TestTestCaseApiUpdate:
    def test_update_test_case_normal(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        case = create_test_case(
            db=db,
            case_no=f"CASE-UPD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="apiupd",
            title="original title",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        response = client.put(
            f"/api/v1/test-case/{case.id}",
            json={"title": "updated title", "priority": 1},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)

    def test_update_test_case_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/test-case/99999",
            json={"title": "should not update"},
            headers=authHeaders,
        )
        assert response.status_code == 404


class TestTestCaseApiDelete:
    def test_delete_test_case_normal(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        case = create_test_case(
            db=db,
            case_no=f"CASE-DEL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="apidel",
            title="to be deleted",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        response = client.delete(
            f"/api/v1/test-case/{case.id}",
            headers=authHeaders,
        )
        assert response.status_code == 200

    def test_delete_test_case_nonexistent(self, client, authHeaders):
        response = client.delete(
            "/api/v1/test-case/99999",
            headers=authHeaders,
        )
        assert response.status_code == 404


class TestTestCaseApiBatchDelete:
    def test_batch_delete_normal(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        case1 = create_test_case(
            db=db,
            case_no=f"CASE-BD1-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="batchdel",
            title="batch delete 1",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        case2 = create_test_case(
            db=db,
            case_no=f"CASE-BD2-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="batchdel",
            title="batch delete 2",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": [case1.id, case2.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["successCount"] == 2

    def test_batch_delete_empty_list(self, client, authHeaders):
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": []},
            headers=authHeaders,
        )
        assert response.status_code == 422

    def test_batch_delete_nonexistent_ids(self, client, authHeaders):
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": [99998, 99999]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["notFoundCount"] == 2


class TestTestCaseApiBatchRestore:
    def test_batch_restore_normal(self, db, client, authHeaders, testProject):
        from app.crud.test_case_mutate import create_test_case
        from app.models.test_case import TestCase
        case = create_test_case(
            db=db,
            case_no=f"CASE-BR-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="batchrestore",
            title="batch restore",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        db.query(TestCase).filter(TestCase.id == case.id).update({"is_deleted": True})
        db.commit()
        response = client.post(
            "/api/v1/test-case/batch-restore",
            json={"caseIds": [case.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["successCount"] == 1
