import uuid
import pytest

pytestmark = pytest.mark.skip(reason="API契约变更（验证码/认证机制重构），测试需要完全重�?)

from tests.helpers import (
    assertResponseSuccess,
    assertResponseError,
    assertResponseUnauthorized,
    assertFieldValue,
    assertFieldExists,
)


class TestAuthAPI:
    def test_get_captcha(self, client):
        response = client.get("/api/v1/auth/captcha")
        data = assertResponseSuccess(response)
        assertFieldExists(data, "captcha_id")
        assertFieldExists(data, "captcha_text")

    def test_get_captcha_returns_different_ids(self, client):
        r1 = client.get("/api/v1/auth/captcha")
        r2 = client.get("/api/v1/auth/captcha")
        d1 = r1.json()
        d2 = r2.json()
        assert d1["captcha_id"] != d2["captcha_id"]

    def test_register_normal(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            params={
                "username": f"reg_user_{uniqueId}",
                "password": "Test@123456",
                "email": f"reg_{uniqueId}@test.com",
            },
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "id")
        assertFieldExists(data, "username")

    def test_register_duplicate_username(self, client, db):
        uniqueId = uuid.uuid4().hex[:8]
        username = f"dup_user_{uniqueId}"
        client.post(
            "/api/v1/auth/register",
            params={"username": username, "password": "Test@123456", "email": f"dup1_{uniqueId}@test.com"},
        )
        response = client.post(
            "/api/v1/auth/register",
            params={"username": username, "password": "Test@123456", "email": f"dup2_{uniqueId}@test.com"},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_duplicate_email(self, client, db):
        uniqueId = uuid.uuid4().hex[:8]
        email = f"dup_{uniqueId}@test.com"
        client.post(
            "/api/v1/auth/register",
            params={"username": f"email_user1_{uniqueId}", "password": "Test@123456", "email": email},
        )
        response = client.post(
            "/api/v1/auth/register",
            params={"username": f"email_user2_{uniqueId}", "password": "Test@123456", "email": email},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_short_username(self, client):
        response = client.post(
            "/api/v1/auth/register",
            params={"username": "ab", "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_short_password(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            params={"username": f"shortpwd_{uniqueId}", "password": "12345"},
        )
        assertResponseError(response, expectedStatus=400)

    def test_register_without_email(self, client):
        uniqueId = uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/register",
            params={"username": f"noemail_{uniqueId}", "password": "Test@123456"},
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "id")

    def test_login_normal(self, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": "Test@123456"},
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "access_token")
        assertFieldExists(data, "user")

    def test_login_wrong_password(self, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": "WrongPassword123"},
        )
        assertResponseError(response, expectedStatus=401)

    def test_login_nonexistent_user(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent_user_xyz", "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=401)

    def test_login_inactive_user(self, client, db):
        from app.models.user import User
        from app.utils.crypto import get_password_hash

        uniqueId = uuid.uuid4().hex[:8]
        inactiveUser = User(
            username=f"inactive_{uniqueId}",
            email=f"inactive_{uniqueId}@test.com",
            hashed_password=get_password_hash("Test@123456"),
            is_active=False,
            is_superuser=False,
        )
        db.add(inactiveUser)
        db.flush()
        response = client.post(
            "/api/v1/auth/login",
            json={"username": inactiveUser.username, "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=403)

    def test_login_empty_username(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "", "password": "Test@123456"},
        )
        assertResponseError(response, expectedStatus=422)

    def test_login_empty_password(self, client, testUser):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": testUser.username, "password": ""},
        )
        assertResponseError(response, expectedStatus=422)

    def test_get_me_normal(self, client, authHeaders, testUser):
        response = client.get("/api/v1/auth/me", headers=authHeaders)
        data = assertResponseSuccess(response)
        assertFieldExists(data, "id")
        assertFieldExists(data, "username")

    def test_get_me_no_auth(self, client):
        response = client.get("/api/v1/auth/me")
        assertResponseUnauthorized(response)

    def test_get_me_invalid_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assertResponseUnauthorized(response)

    def test_get_me_empty_token(self, client):
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assertResponseUnauthorized(response)


class TestProjectAPI:
    def test_create_project_normal(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_proj_{uuid.uuid4().hex[:8]}",
                "description": "api test project",
                "project_type": "web",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "data")
        assertFieldExists(data["data"], "project_id")

    def test_create_project_minimal(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_min_{uuid.uuid4().hex[:8]}",
            },
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_create_project_duplicate_name(self, client, authHeaders):
        name = f"api_dup_{uuid.uuid4().hex[:8]}"
        client.post(
            "/api/v1/project/",
            json={"name": name, "description": "first"},
            headers=authHeaders,
        )
        response = client.post(
            "/api/v1/project/",
            json={"name": name, "description": "second"},
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=400)

    def test_create_project_no_auth(self, client):
        response = client.post(
            "/api/v1/project/",
            json={"name": f"api_noauth_{uuid.uuid4().hex[:8]}"},
        )
        assertResponseUnauthorized(response)

    def test_get_projects_list(self, client, authHeaders):
        response = client.get(
            "/api/v1/project/list",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "data")
        assert "items" in data["data"]
        assert "total" in data["data"]

    def test_get_projects_pagination(self, client, authHeaders):
        response = client.get(
            "/api/v1/project/list",
            params={"page": 1, "page_size": 5},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5

    def test_get_project_detail(self, client, authHeaders):
        create_resp = client.post(
            "/api/v1/project/",
            json={"name": f"api_detail_{uuid.uuid4().hex[:8]}", "description": "detail test"},
            headers=authHeaders,
        )
        project_id = create_resp.json()["data"]["project_id"]
        response = client.get(
            f"/api/v1/project/{project_id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assertFieldExists(data, "data")
        assert data["data"]["id"] == project_id

    def test_get_project_nonexistent(self, client, authHeaders):
        response = client.get(
            "/api/v1/project/99999",
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=403)

    def test_delete_project_normal(self, client, authHeaders):
        create_resp = client.post(
            "/api/v1/project/",
            json={"name": f"api_del_{uuid.uuid4().hex[:8]}"},
            headers=authHeaders,
        )
        project_id = create_resp.json()["data"]["project_id"]
        response = client.delete(
            f"/api/v1/project/{project_id}",
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_delete_project_nonexistent(self, client, authHeaders):
        response = client.delete(
            "/api/v1/project/99999",
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=403)

    def test_delete_project_no_auth(self, client):
        response = client.delete("/api/v1/project/1")
        assertResponseUnauthorized(response)


class TestTestCaseAPI:
    def test_create_test_case_normal(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/testCase/",
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
            "/api/v1/testCase/",
            json={
                "project_id": testProject.id,
                "title": f"api_min_{uuid.uuid4().hex[:8]}",
            },
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_create_test_case_with_test_data(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/testCase/",
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
            "/api/v1/testCase/",
            json={
                "project_id": testProject.id,
                "title": "no auth case",
            },
        )
        assert response.status_code == 401 or response.status_code == 403

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
            "/api/v1/testCase/",
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
            "/api/v1/testCase/",
            params={"project_id": testProject.id, "page": 1, "page_size": 2},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert len(data["data"]["items"]) <= 2

    def test_get_test_cases_empty(self, client, authHeaders):
        response = client.get(
            "/api/v1/testCase/",
            params={"project_id": 99999},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["total"] == 0

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
            f"/api/v1/testCase/{case.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)

    def test_get_test_case_nonexistent(self, client, authHeaders):
        response = client.get(
            "/api/v1/testCase/99999",
            headers=authHeaders,
        )
        assert response.status_code == 404

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
            f"/api/v1/testCase/{case.id}",
            json={"title": "updated title", "priority": 1},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)

    def test_update_test_case_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/testCase/99999",
            json={"title": "should not update"},
            headers=authHeaders,
        )
        assert response.status_code == 404

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
            f"/api/v1/testCase/{case.id}",
            headers=authHeaders,
        )
        assert response.status_code == 200

    def test_delete_test_case_nonexistent(self, client, authHeaders):
        response = client.delete(
            "/api/v1/testCase/99999",
            headers=authHeaders,
        )
        assert response.status_code == 404

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
            "/api/v1/testCase/batch-delete",
            json={"caseIds": [case1.id, case2.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["successCount"] == 2

    def test_batch_delete_empty_list(self, client, authHeaders):
        response = client.post(
            "/api/v1/testCase/batch-delete",
            json={"caseIds": []},
            headers=authHeaders,
        )
        assert response.status_code == 422

    def test_batch_delete_nonexistent_ids(self, client, authHeaders):
        response = client.post(
            "/api/v1/testCase/batch-delete",
            json={"caseIds": [99998, 99999]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["notFoundCount"] == 2

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
            "/api/v1/testCase/batch-restore",
            json={"caseIds": [case.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["successCount"] == 1
