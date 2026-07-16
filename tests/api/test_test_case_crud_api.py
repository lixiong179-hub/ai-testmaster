import pytest
from sqlalchemy import select
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
    """test_case_crud.py 端点测试。

    5 个迁移端点用 async fixture 测试；2 个 batch 端点（来自 test_case_crud_batch.py，
    未迁移）保留 sync fixture 测试。
    """

    async def test_create_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-case/",
            json={"project_id": 1, "title": "测试"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_list_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/")
        assert resp.status_code in (401, 403, 404)

    async def test_get_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1")
        assert resp.status_code in (401, 403, 404)

    async def test_update_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/test-case/1",
            json={"title": "更新"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_delete_without_auth(self, async_client):
        resp = await async_client.delete("/api/v1/test-case/1")
        assert resp.status_code in (401, 403, 404)

    async def test_list_with_auth(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            "/api/v1/test-case/",
            params={"project_id": async_test_project.id, "page": 1, "page_size": 10},
        )
        assert resp.status_code in (200, 404, 500)

    async def test_list_accepts_page_filters_and_legacy_step_shapes(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-LIST-FILTER-LEGACY",
            project_id=async_test_project.id,
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
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.get(
            "/api/v1/test-case/",
            params={
                "project_id": async_test_project.id,
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
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] >= 1
        assert data["stats"]["high_priority"] >= 1
        assert any(item["id"] == case.id for item in data["items"])

    async def test_get_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-case/99999")
        assert resp.status_code in (404, 500)

    async def test_delete_with_project_scope(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-DELETE-SCOPE",
            project_id=async_test_project.id,
            module="scope",
            title="delete scoped case",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.delete(
            f"/api/v1/test-case/{case.id}",
            params={"project_id": async_test_project.id},
        )

        assert resp.status_code == 200, resp.text
        await async_db.refresh(case)
        assert case.is_deleted is True

    # 以下 2 个测试针对 test_case_crud_batch.py 的 batch 端点（已迁移至 async，Task 15）。
    async def test_batch_delete_with_project_scope(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-BATCH-DELETE-SCOPE",
            project_id=async_test_project.id,
            module="scope",
            title="batch delete scoped case",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.post(
            "/api/v1/test-case/batch-delete",
            json={"project_id": async_test_project.id, "caseIds": [case.id]},
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["deleted_ids"] == [case.id]
        await async_db.refresh(case)
        assert case.is_deleted is True

    async def test_batch_restore_with_project_scope(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            case_no="CASE-BATCH-RESTORE-SCOPE",
            project_id=async_test_project.id,
            module="scope",
            title="batch restore scoped case",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
            is_deleted=True,
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.post(
            "/api/v1/test-case/batch-restore",
            json={"project_id": async_test_project.id, "caseIds": [case.id]},
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["restored_ids"] == [case.id]
        await async_db.refresh(case)
        assert case.is_deleted is False
