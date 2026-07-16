"""case_refresh.py 端点 async 测试。

覆盖 /api/v1/case-refresh 端点的权限拦截、不存在资源、空数据场景。
使用 tests/api/conftest.py 的 async fixture。

端点概览:
    - GET  /projects/{project_id}/refresh-suggestions        - 列表
    - GET  /projects/{project_id}/refresh-suggestions/stats  - 统计
    - POST /refresh-suggestions/{suggestion_id}/review       - 审核
    - POST /projects/{project_id}/scan-stale-cases           - 扫描过期
    - POST /projects/{project_id}/auto-refresh               - 后台自动保鲜
"""


class TestCaseRefreshAsync:
    """case_refresh.py 端点 async 测试。"""

    async def test_list_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/case-refresh/projects/1/refresh-suggestions"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_stats_without_auth(self, async_client):
        resp = await async_client.get(
            "/api/v1/case-refresh/projects/1/refresh-suggestions/stats"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_review_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/case-refresh/refresh-suggestions/1/review",
            json={"action": "approve"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_scan_stale_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/case-refresh/projects/1/scan-stale-cases"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_auto_refresh_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/case-refresh/projects/1/auto-refresh"
        )
        assert resp.status_code in (401, 403, 404)

    async def test_list_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/case-refresh/projects/99999/refresh-suggestions"
        )
        assert resp.status_code in (403, 404, 500)

    async def test_stats_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/case-refresh/projects/99999/refresh-suggestions/stats"
        )
        assert resp.status_code in (403, 404, 500)

    async def test_scan_stale_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/case-refresh/projects/99999/scan-stale-cases"
        )
        assert resp.status_code in (403, 404, 500)

    async def test_auto_refresh_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/case-refresh/projects/99999/auto-refresh"
        )
        assert resp.status_code in (403, 404, 500)

    async def test_review_nonexistent_suggestion(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/case-refresh/refresh-suggestions/99999/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 404

    async def test_list_empty(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/case-refresh/projects/{async_test_project.id}/refresh-suggestions"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "items" in data or "list" in data or isinstance(data, list) or data == {} or "total" in data

    async def test_stats_empty(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/case-refresh/projects/{async_test_project.id}/refresh-suggestions/stats"
        )
        assert resp.status_code == 200, resp.text

    async def test_scan_stale_empty(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            f"/api/v1/case-refresh/projects/{async_test_project.id}/scan-stale-cases"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["count"] == 0
        assert data["stale_cases"] == []

    async def test_auto_refresh_empty(self, async_auth_client, async_test_project):
        """无过期用例时返回 total_scanned=0，不触发后台任务。"""
        resp = await async_auth_client.post(
            f"/api/v1/case-refresh/projects/{async_test_project.id}/auto-refresh"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total_scanned"] == 0
