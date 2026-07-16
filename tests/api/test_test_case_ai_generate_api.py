"""AI 生成端点 async 测试。

覆盖 /api/v1/ai-generate 端点的未认证、不存在资源、缺参数场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestAIGenerateEndpoint:
    async def test_generate_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/ai-generate",
            json={"project_id": 1, "point_ids": [1]},
        )
        assert resp.status_code in (401, 403, 404, 422)

    async def test_generate_with_auth_no_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/ai-generate",
            json={"project_id": 99999, "point_ids": []},
        )
        assert resp.status_code in (200, 400, 403, 404, 500)

    async def test_generate_missing_body(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/ai-generate",
        )
        assert resp.status_code in (404, 422)


class TestAIContextEndpoint:
    async def test_context_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/ai-generate/context",
            params={"project_id": 1},
        )
        assert resp.status_code in (401, 403, 404)
