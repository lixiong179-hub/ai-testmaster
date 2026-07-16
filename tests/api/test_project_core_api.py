"""project_core.py 端点 async 测试。

覆盖 POST/GET/DELETE /api/v1/project/ 端点的未认证、正常、异常场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestProjectCoreAPI:
    """项目核心 CRUD 端点测试。"""

    async def test_list_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/project/list")
        assert resp.status_code in (401, 403, 404)

    async def test_detail_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/project/1")
        assert resp.status_code in (401, 403, 404)

    async def test_create_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/project/create",
            json={"name": "test", "project_type": "web"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_delete_without_auth(self, async_client):
        resp = await async_client.delete("/api/v1/project/1")
        assert resp.status_code in (401, 403, 404)

    async def test_list_authenticated(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get("/api/v1/project/list")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "items" in data
        assert "total" in data

    async def test_detail_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/project/99999")
        assert resp.status_code in (403, 404)

    async def test_detail_owned(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(f"/api/v1/project/{async_test_project.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == async_test_project.id
        assert data["name"] == async_test_project.name

    async def test_create_duplicate_name(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/project/create",
            json={"name": async_test_project.name, "project_type": "web"},
        )
        assert resp.status_code in (400, 500)

    async def test_delete_nonexistent(self, async_auth_client):
        resp = await async_auth_client.delete("/api/v1/project/99999")
        assert resp.status_code in (403, 404)
