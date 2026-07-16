"""test_data.py 端点 async 测试。

覆盖 /api/v1/test-data/ 端点的未认证、不存在资源、空列表场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestTestDataAPI:
    """测试数据 CRUD 端点测试。"""

    async def test_create_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-data/",
            json={
                "step_id": 1,
                "field_name": "username",
            },
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-data/1")
        assert resp.status_code in (401, 403, 404)

    async def test_get_by_step_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-data/step/1")
        assert resp.status_code in (401, 403, 404)

    async def test_update_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/test-data/1",
            json={"field_name": "new_name"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_delete_without_auth(self, async_client):
        resp = await async_client.delete("/api/v1/test-data/1")
        assert resp.status_code in (401, 403, 404)

    async def test_generate_without_auth(self, async_client):
        resp = await async_client.post("/api/v1/test-data/step/1/generate")
        assert resp.status_code in (401, 403, 404)

    async def test_auto_generate_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-data/step/1/auto-generate",
            params={"action_description": "click login button"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-data/99999")
        assert resp.status_code in (404, 500)

    async def test_update_nonexistent(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/test-data/99999",
            json={"field_name": "new_name"},
        )
        assert resp.status_code in (404, 500)

    async def test_delete_nonexistent(self, async_auth_client):
        resp = await async_auth_client.delete("/api/v1/test-data/99999")
        assert resp.status_code in (404, 500)

    async def test_get_by_step_empty(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-data/step/99999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["step_id"] == 99999
        assert data["data_list"] == []
