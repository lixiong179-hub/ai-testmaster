import pytest
from app.api.v1.endpoints.test_case_crud import merge_test_data_to_steps
from app.schemas.test_case import TestCaseCreate, TestCaseStep

TestCaseCreate.__test__ = False
TestCaseStep.__test__ = False


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

    def test_list_accepts_page_filters_and_legacy_step_shapes(self, db, client, authHeaders, testProject):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-LIST-FILTER-LEGACY",
            project_id=testProject.id,
            module="login",
            title="login page legacy step shape",
            precondition="none",
            steps_json=[
                {
                    "step": 1,
                    "action": "click login",
                    "expected_result": "success",
                    "ui_elements": [{"type": "button", "label": "Login"}],
                    "test_data": [{"field_name": "username", "data_value": "admin"}],
                }
            ],
            expected_result="ok",
            priority=1,
            case_type="ui_automation",
            lifecycle_status="draft",
        )
        db.add(case)
        db.flush()

        resp = client.get(
            "/api/v1/testCase/",
            params={
                "project_id": testProject.id,
                "keyword": "legacy",
                "module": "login",
                "priority": 1,
                "case_type": "ui_automation",
                "status": "draft",
                "sort_by": "priority",
                "sort_order": "asc",
                "page": 1,
                "page_size": 20,
            },
            headers=authHeaders,
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] >= 1
        assert data["stats"]["high_priority"] >= 1
        assert any(item["id"] == case.id for item in data["items"])

    def test_get_nonexistent(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)

    def test_delete_with_project_scope(self, db, client, authHeaders, testProject):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-DELETE-SCOPE",
            project_id=testProject.id,
            module="scope",
            title="delete scoped case",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
        )
        db.add(case)
        db.flush()

        resp = client.delete(
            f"/api/v1/testCase/{case.id}",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )

        assert resp.status_code == 200, resp.text
        db.refresh(case)
        assert case.is_deleted is True

    def test_batch_delete_with_project_scope(self, db, client, authHeaders, testProject):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-BATCH-DELETE-SCOPE",
            project_id=testProject.id,
            module="scope",
            title="batch delete scoped case",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
        )
        db.add(case)
        db.flush()

        resp = client.post(
            "/api/v1/testCase/batch-delete",
            json={"project_id": testProject.id, "caseIds": [case.id]},
            headers=authHeaders,
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["deleted_ids"] == [case.id]
        db.refresh(case)
        assert case.is_deleted is True

    def test_batch_restore_with_project_scope(self, db, client, authHeaders, testProject):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-BATCH-RESTORE-SCOPE",
            project_id=testProject.id,
            module="scope",
            title="batch restore scoped case",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
            is_deleted=True,
        )
        db.add(case)
        db.flush()

        resp = client.post(
            "/api/v1/testCase/batch-restore",
            json={"project_id": testProject.id, "caseIds": [case.id]},
            headers=authHeaders,
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["restored_ids"] == [case.id]
        db.refresh(case)
        assert case.is_deleted is False
