"""visibility 端点 async 测试。

覆盖 /api/v1/visibility/config 端点的查询与更新场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestVisibilityAPI:
    """可见性配置端点测试。"""

    async def test_get_global_config(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/visibility/config?level=global")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert "headless" in data["data"]

    async def test_get_task_config_no_id(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/visibility/config?level=task")
        assert resp.status_code == 200

    async def test_get_case_config_no_id(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/visibility/config?level=case")
        assert resp.status_code == 200

    async def test_get_unknown_level_defaults_to_global(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/visibility/config?level=unknown")
        assert resp.status_code == 200

    async def test_update_global_config(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/visibility/config",
            json={
                "level": "global",
                "headless": False,
                "record_video": True,
                "execution_speed": "fast",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["headless"] is False

    async def test_update_invalid_config_rejected(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/visibility/config",
            json={
                "level": "global",
                "execution_speed": "turbo",
            },
        )
        assert resp.status_code == 400

    async def test_update_task_config_not_found(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/visibility/config",
            json={
                "level": "task",
                "id": 99999,
                "headless": True,
            },
        )
        assert resp.status_code == 404

    async def test_update_case_config_not_found(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/visibility/config",
            json={
                "level": "case",
                "id": 99999,
                "headless": True,
            },
        )
        assert resp.status_code == 404

    async def test_unauthenticated_access(self, async_client):
        resp = await async_client.get("/api/v1/visibility/config?level=global")
        assert resp.status_code in (401, 403)
