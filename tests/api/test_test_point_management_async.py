"""test_point/_management.py 端点 async 测试。

覆盖 /api/v1/test-point/ 端点的未认证、不存在资源、正常场景。
使用 tests/api/conftest.py 的 async fixture。

端点概览:
    - POST /                                    - 创建测试点
    - GET  /{test_point_id}/test-cases          - 获取测试点关联用例
    - GET  /requirements/{project_id}           - 获取项目需求选项
    - POST /batch-generate-cases/stream         - 批量生成用例（SSE，仅测权限拦截）
"""
import uuid

from app.crud.test_point import create_test_point
from app.models.requirement import Requirement
from tests.helpers import createTestTestCase


class TestTestPointManagementAsync:
    """test_point/_management.py 端点 async 测试。"""

    async def test_create_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-point/",
            json={"project_id": 1, "module": "M", "point": "测试点"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_test_cases_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/test-point/1/test-cases",
            params={"project_id": 1},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_requirements_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-point/requirements/1")
        assert resp.status_code in (401, 403, 404)

    async def test_batch_generate_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-point/batch-generate-cases/stream",
            json={"project_id": 1},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_create_for_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/test-point/",
            json={"project_id": 99999, "module": "M", "point": "测试点", "priority": 1},
        )
        assert resp.status_code in (403, 404, 500)

    async def test_create_success(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/test-point/",
            json={
                "project_id": async_test_project.id,
                "module": "async_module",
                "point": "async 测试点",
                "priority": 1,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["project_id"] == async_test_project.id
        assert data["module"] == "async_module"
        assert data["point"] == "async 测试点"

    async def test_get_test_cases_nonexistent_point(
        self, async_auth_client, async_test_project
    ):
        resp = await async_auth_client.get(
            "/api/v1/test-point/99999/test-cases",
            params={"project_id": async_test_project.id},
        )
        assert resp.status_code in (404, 500)

    async def test_get_test_cases_empty(
        self, async_db, async_auth_client, async_test_project
    ):
        def _create_point(sync_db):
            return create_test_point(
                db=sync_db, project_id=async_test_project.id,
                module="empty_module", point="empty point",
                priority=2, created_by="async_test_user",
            )

        point = await async_db.run_sync(_create_point)
        await async_db.flush()

        resp = await async_auth_client.get(
            f"/api/v1/test-point/{point.id}/test-cases",
            params={"project_id": async_test_project.id},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["items"] == []

    async def test_get_requirements_empty(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/test-point/requirements/{async_test_project.id}"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["items"] == []

    async def test_get_requirements_with_data(
        self, async_db, async_auth_client, async_test_project
    ):
        requirement = Requirement(
            project_id=async_test_project.id,
            req_no=f"REQ-{uuid.uuid4().hex[:8]}",
            title="async requirement",
            description="test",
            priority=1,
            status="draft",
        )
        async_db.add(requirement)
        await async_db.flush()

        resp = await async_auth_client.get(
            f"/api/v1/test-point/requirements/{async_test_project.id}"
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        assert any(item["id"] == requirement.id for item in items)

    async def test_batch_generate_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/test-point/batch-generate-cases/stream",
            json={"project_id": 99999},
        )
        assert resp.status_code in (403, 404, 500)
