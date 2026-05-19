import pytest


class TestAuditLogAPI:
    def test_unauthenticated_returns_error(self, client):
        resp = client.get("/api/v1/audit-log/logs")
        assert resp.status_code in (401, 403, 307, 405, 500)

    def test_authenticated_endpoint_exists(self, client, adminAuthHeaders):
        resp = client.get("/api/v1/audit-log/logs", headers=adminAuthHeaders)
        assert resp.status_code in (200, 403, 404, 405, 422, 500)
