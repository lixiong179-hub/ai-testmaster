import uuid
import pytest

# pytestmark = pytest.mark.skip(reason="API契约变更（认证/测试用例接口重构），测试需要完全重写")  # 临时移除排查

from tests.helpers import (
    assertResponseSuccess,
    assertResponseError,
    assertResponseUnauthorized,
    assertFieldExists,
    assertFieldValue,
    createTestTestCase,
    createTestProject,
    createTestUser,
    getAuthHeaders,
)


def _build_test_case_payload(projectId: int, **overrides) -> dict:
    payload = {
        "project_id": projectId,
        "title": f"api_case_{uuid.uuid4().hex[:8]}",
        "module": "api_test_module",
        "precondition": "none",
        "steps": [
            {
                "step": 1,
                "action": "open page",
                "param": "",
                "expected_result": "page loaded",
            }
        ],
        "expected_result": "test passes",
        "priority": 2,
        "case_type": "ui_automation",
    }
    payload.update(overrides)
    return payload


class TestCreateTestCase:
    def test_create_test_case_normal(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json=_build_test_case_payload(testProject.id),
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")
        assertFieldExists(data, "title")

    def test_create_test_case_with_case_no(self, client, authHeaders, testProject):
        caseNo = f"API-CASE-{uuid.uuid4().hex[:8]}"
        response = client.post(
            "/api/v1/test-case/",
            json=_build_test_case_payload(testProject.id, case_no=caseNo),
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "case_no", caseNo)

    def test_create_test_case_with_test_data(self, client, authHeaders, testProject):
        payload = _build_test_case_payload(testProject.id)
        payload["steps"][0]["test_data"] = {
            "field_name": "username",
            "field_type": "text",
            "data_value": "admin",
        }
        response = client.post(
            "/api/v1/test-case/",
            json=payload,
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")

    def test_create_test_case_no_auth(self, client, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json=_build_test_case_payload(testProject.id),
        )
        assertResponseUnauthorized(response)

    def test_create_test_case_with_test_category(self, client, authHeaders, testProject):
        response = client.post(
            "/api/v1/test-case/",
            json=_build_test_case_payload(testProject.id, test_category="ui_automation"),
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")

    def test_create_test_case_boundary_priority(self, client, authHeaders, testProject):
        for priority in [1, 2, 3]:
            response = client.post(
                "/api/v1/test-case/",
                json=_build_test_case_payload(testProject.id, priority=priority),
                headers=authHeaders,
            )
            data = assertResponseSuccess(response)["data"]
            assertFieldValue(data, "priority", priority)


class TestGetTestCases:
    def test_get_test_cases_normal(self, client, authHeaders, testProject):
        response = client.get(
            "/api/v1/test-case/",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "items")
        assertFieldExists(data, "total")

    def test_get_test_cases_with_project_filter(self, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/test-case/?project_id={testProject.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "items")

    def test_get_test_cases_pagination(self, client, authHeaders, testProject):
        response = client.get(
            "/api/v1/test-case/?page=1&page_size=5",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "items")

    def test_get_test_cases_no_auth(self, client):
        response = client.get("/api/v1/test-case/")
        assertResponseUnauthorized(response)


class TestGetTestCase:
    def test_get_test_case_normal(self, client, authHeaders, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id, title="api get case")
        response = client.get(
            f"/api/v1/test-case/{testCase.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")

    def test_get_test_case_nonexistent(self, client, authHeaders):
        response = client.get(
            "/api/v1/test-case/99999",
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=404)

    def test_get_test_case_no_auth(self, client, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id)
        response = client.get(f"/api/v1/test-case/{testCase.id}")
        assertResponseUnauthorized(response)


class TestUpdateTestCase:
    def test_update_test_case_normal(self, client, authHeaders, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id, title="original title")
        response = client.put(
            f"/api/v1/test-case/{testCase.id}",
            json={"title": "updated title", "priority": 1},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "title", "updated title")
        assertFieldValue(data, "priority", 1)

    def test_update_test_case_with_steps(self, client, authHeaders, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id)
        # TestCaseStep schema 要求 step 字段 (步骤描述或编号)
        newSteps = [
            {"step": 1, "action": "click button", "expected_result": "button clicked", "action_type": "click"},
            {"step": 2, "action": "verify text", "expected_result": "text visible", "action_type": "verify"},
        ]
        response = client.put(
            f"/api/v1/test-case/{testCase.id}",
            json={"steps": newSteps},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "steps")

    def test_update_test_case_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/test-case/99999",
            json={"title": "should not update"},
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=404)

    def test_update_test_case_no_auth(self, client, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id)
        response = client.put(
            f"/api/v1/test-case/{testCase.id}",
            json={"title": "should not update"},
        )
        assertResponseUnauthorized(response)

    def test_update_test_case_module(self, client, authHeaders, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id)
        response = client.put(
            f"/api/v1/test-case/{testCase.id}",
            json={"module": "updated_module"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "module", "updated_module")


class TestDeleteTestCase:
    def test_delete_test_case_normal(self, client, authHeaders, db, testProject, testUser):
        testCase = createTestTestCase(db=db, projectId=testProject.id, title="to delete")
        response = client.delete(
            f"/api/v1/test-case/{testCase.id}",
            headers=authHeaders,
        )
        assert response.status_code == 200

    def test_delete_test_case_nonexistent(self, client, authHeaders):
        response = client.delete(
            "/api/v1/test-case/99999",
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=404)

    def test_delete_test_case_no_auth(self, client, db, testProject):
        testCase = createTestTestCase(db=db, projectId=testProject.id)
        response = client.delete(f"/api/v1/test-case/{testCase.id}")
        assertResponseUnauthorized(response)


class TestBatchDeleteTestCases:
    def test_batch_delete_normal(self, client, authHeaders, db, testProject, testUser):
        tc1 = createTestTestCase(db=db, projectId=testProject.id)
        tc2 = createTestTestCase(db=db, projectId=testProject.id)
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": [tc1.id, tc2.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "success_count")

    def test_batch_delete_nonexistent_ids(self, client, authHeaders):
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": [99998, 99999]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "success_count", 0)

    def test_batch_delete_empty_list(self, client, authHeaders):
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": []},
            headers=authHeaders,
        )
        # Pydantic value_error 被全局异常处理器包装为 400 (非 422)
        assertResponseError(response, expectedStatus=400)

    def test_batch_delete_no_auth(self, client):
        response = client.post(
            "/api/v1/test-case/batch-delete",
            json={"caseIds": [1]},
        )
        assertResponseUnauthorized(response)


class TestBatchRestoreTestCases:
    def test_batch_restore_normal(self, client, authHeaders, db, testProject, testUser):
        tc1 = createTestTestCase(db=db, projectId=testProject.id)
        tc2 = createTestTestCase(db=db, projectId=testProject.id)
        from app.models.test_case import TestCase
        from datetime import datetime as dt

        db.query(TestCase).filter(TestCase.id.in_([tc1.id, tc2.id])).update(
            {"is_deleted": True, "deleted_at": dt.utcnow()}, synchronize_session="fetch"
        )
        db.flush()
        response = client.post(
            "/api/v1/test-case/batch-restore",
            json={"caseIds": [tc1.id, tc2.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "success_count")

    def test_batch_restore_non_deleted_cases(self, client, authHeaders, db, testProject, testUser):
        tc = createTestTestCase(db=db, projectId=testProject.id)
        response = client.post(
            "/api/v1/test-case/batch-restore",
            json={"caseIds": [tc.id]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "not_found_count", 1)

    def test_batch_restore_nonexistent_ids(self, client, authHeaders):
        response = client.post(
            "/api/v1/test-case/batch-restore",
            json={"caseIds": [99998, 99999]},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "not_found_count", 2)

    def test_batch_restore_empty_list(self, client, authHeaders):
        response = client.post(
            "/api/v1/test-case/batch-restore",
            json={"caseIds": []},
            headers=authHeaders,
        )
        # Pydantic value_error 被全局异常处理器包装为 400 (非 422)
        assertResponseError(response, expectedStatus=400)

    def test_batch_restore_no_auth(self, client):
        response = client.post(
            "/api/v1/test-case/batch-restore",
            json={"caseIds": [1]},
        )
        assertResponseUnauthorized(response)
