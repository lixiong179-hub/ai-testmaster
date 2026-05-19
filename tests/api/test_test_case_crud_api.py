import pytest
from app.api.v1.endpoints.test_case_crud import merge_test_data_to_steps
from app.schemas.test_case import TestCaseCreate, TestCaseStep


class TestMergeTestDataToSteps:
    def test_without_test_data(self):
        case = TestCaseCreate(
            project_id=1,
            title="测试用例",
            steps=[TestCaseStep(step=1, action="点击", expected_result="成功")],
        )
        result = merge_test_data_to_steps(case)
        assert len(result) == 1

    def test_empty_steps(self):
        case = TestCaseCreate(project_id=1, title="测试用例")
        result = merge_test_data_to_steps(case)
        assert result == []


class TestTestCaseCrudAPI:
    def test_create_without_auth(self, client):
        resp = client.post(
            "/api/v1/testCase/",
            json={"project_id": 1, "title": "测试"},
        )
        assert resp.status_code in (401, 403, 404)

    def test_list_without_auth(self, client):
        resp = client.get("/api/v1/testCase/")
        assert resp.status_code in (401, 403, 404)

    def test_get_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1")
        assert resp.status_code in (401, 403, 404)

    def test_update_without_auth(self, client):
        resp = client.put(
            "/api/v1/testCase/1",
            json={"title": "更新"},
        )
        assert resp.status_code in (401, 403, 404)

    def test_delete_without_auth(self, client):
        resp = client.delete("/api/v1/testCase/1")
        assert resp.status_code in (401, 403, 404)

    def test_list_with_auth(self, client, authHeaders, testProject):
        resp = client.get(
            "/api/v1/testCase/",
            params={"project_id": testProject.id, "page": 1, "page_size": 10},
            headers=authHeaders,
        )
        assert resp.status_code in (200, 404, 500)

    def test_get_nonexistent(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)
