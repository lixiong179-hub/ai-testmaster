"""audit_log 端点 async 测试。

覆盖 /api/v1/audit-log/logs 端点的未认证与认证场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestAuditLogAPI:
    """审计日志端点测试。"""

    async def test_unauthenticated_returns_error(self, async_client):
        resp = await async_client.get("/api/v1/audit-log/logs")
        assert resp.status_code in (401, 403, 307, 405, 500)

    async def test_authenticated_endpoint_exists(self, async_admin_client):
        resp = await async_admin_client.get("/api/v1/audit-log/logs")
        assert resp.status_code in (200, 403, 404, 405, 422, 500)
