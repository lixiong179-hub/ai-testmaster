"""test_capability 端点 async 测试。

覆盖 /api/v1/test-capability/ 端点的 CRUD 与边界场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestCapabilityAPI:
    """测试能力 CRUD 端点测试。"""

    async def test_list_capabilities(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/test-capability/?project_id={async_test_project.id}",
        )
        assert resp.status_code == 200

    async def test_create_capability(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "API_TEST_CAP",
                "title": "API测试能力",
                "status": "active",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "API_TEST_CAP"

    async def test_create_duplicate_capability(self, async_auth_client, async_test_project):
        await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "DUP_API_CAP",
                "title": "重复能力",
                "status": "active",
            },
        )
        resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "DUP_API_CAP",
                "title": "重复能力2",
                "status": "active",
            },
        )
        assert resp.status_code == 409

    async def test_get_capability(self, async_auth_client, async_test_project):
        create_resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "GET_CAP",
                "title": "查询能力",
                "status": "active",
            },
        )
        cap_id = create_resp.json()["id"]
        resp = await async_auth_client.get(f"/api/v1/test-capability/{cap_id}")
        assert resp.status_code == 200
        assert resp.json()["key"] == "GET_CAP"

    async def test_get_capability_not_found(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-capability/99999")
        assert resp.status_code == 404

    async def test_update_capability(self, async_auth_client, async_test_project):
        create_resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "UPD_CAP",
                "title": "更新前",
                "status": "active",
            },
        )
        cap_id = create_resp.json()["id"]
        resp = await async_auth_client.put(
            f"/api/v1/test-capability/{cap_id}",
            json={"title": "更新后"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "更新后"

    async def test_delete_capability(self, async_auth_client, async_test_project):
        """软删除返回 200，status 为 archived"""
        create_resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "DEL_CAP",
                "title": "删除能力",
                "status": "active",
            },
        )
        cap_id = create_resp.json()["id"]
        resp = await async_auth_client.delete(f"/api/v1/test-capability/{cap_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"

    async def test_delete_capability_not_found(self, async_auth_client):
        resp = await async_auth_client.delete("/api/v1/test-capability/99999")
        assert resp.status_code == 404

    async def test_list_default_excludes_archived(self, async_auth_client, async_test_project):
        """默认列表不包含已归档能力"""
        create_resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "ARCH_LIST_CAP",
                "title": "待归档",
                "status": "active",
            },
        )
        cap_id = create_resp.json()["id"]
        await async_auth_client.delete(f"/api/v1/test-capability/{cap_id}")

        resp = await async_auth_client.get(
            f"/api/v1/test-capability/?project_id={async_test_project.id}",
        )
        keys = {c["key"] for c in resp.json()["data"]["items"]}
        assert "ARCH_LIST_CAP" not in keys

    async def test_list_include_archived(self, async_auth_client, async_test_project):
        """include_archived=True 时包含已归档能力"""
        create_resp = await async_auth_client.post(
            "/api/v1/test-capability/",
            json={
                "project_id": async_test_project.id,
                "key": "ARCH_INC_CAP",
                "title": "待归档包含",
                "status": "active",
            },
        )
        cap_id = create_resp.json()["id"]
        await async_auth_client.delete(f"/api/v1/test-capability/{cap_id}")

        resp = await async_auth_client.get(
            f"/api/v1/test-capability/?project_id={async_test_project.id}&include_archived=true",
        )
        keys = {c["key"] for c in resp.json()["data"]["items"]}
        assert "ARCH_INC_CAP" in keys

    async def test_unauthenticated(self, async_client, async_test_project):
        resp = await async_client.get(
            f"/api/v1/test-capability/?project_id={async_test_project.id}"
        )
        assert resp.status_code in (401, 403)
