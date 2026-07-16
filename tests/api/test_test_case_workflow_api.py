import pytest


class TestWorkflowEndpoints:
    """test_case_workflow.py 端点测试（technical-view / business-view）。

    注意：test_case_status.py 的 workflow/correction/start-correction/submit-verification
    端点已迁移至 async，对应测试移至 tests/api/test_test_case_status_api.py。
    """

    async def test_technical_view_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1/technical-view")
        assert resp.status_code in (401, 403, 404)

    async def test_business_view_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1/business-view")
        assert resp.status_code in (401, 403, 404)

    async def test_technical_view_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-case/99999/technical-view")
        assert resp.status_code in (403, 404, 500)

    async def test_business_view_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-case/99999/business-view")
        assert resp.status_code in (404, 500)
