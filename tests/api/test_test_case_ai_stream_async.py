"""test_case_ai_stream.py 端点 async 测试。

覆盖 /api/v1/test-case/ai-enhanced-generate/stream 和
/api/v1/test-case/batch-generate/stream 两个 SSE 端点的权限拦截与基础校验。

使用 tests/api/conftest.py 的 async fixture。

端点概览:
    - POST /ai-enhanced-generate/stream - AI增强模式流式生成
    - POST /batch-generate/stream       - 流式批量生成测试用例
"""


class TestCaseAiStreamAsync:
    """test_case_ai_stream.py 端点 async 测试。"""

    async def test_enhanced_generate_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-case/ai-enhanced-generate/stream",
            json={"project_id": 1, "description": "登录功能测试"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_enhanced_generate_unauthorized_project(
        self, async_auth_client
    ):
        resp = await async_auth_client.post(
            "/api/v1/test-case/ai-enhanced-generate/stream",
            json={"project_id": 99999, "description": "登录功能测试"},
        )
        assert resp.status_code in (403, 404, 500)

    async def test_enhanced_generate_short_description(
        self, async_auth_client, async_test_project
    ):
        """描述长度 < 5 应被 400 拒绝（权限校验先通过）。"""
        resp = await async_auth_client.post(
            "/api/v1/test-case/ai-enhanced-generate/stream",
            json={"project_id": async_test_project.id, "description": "ab"},
        )
        assert resp.status_code == 400

    async def test_batch_generate_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/test-case/batch-generate/stream",
            json={"project_id": 1},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_batch_generate_unauthorized_project(
        self, async_auth_client
    ):
        resp = await async_auth_client.post(
            "/api/v1/test-case/batch-generate/stream",
            json={"project_id": 99999},
        )
        assert resp.status_code in (403, 404, 500)
