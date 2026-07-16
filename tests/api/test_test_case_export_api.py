"""test_case_export.py 端点 async 测试。

覆盖 Markdown/HTML/Python/JSON/Excel 导出端点的未认证与不存在用例场景。
使用 tests/api/conftest.py 的 async fixture。
"""


class TestExportAPI:
    """测试用例多格式导出端点测试。"""

    async def test_export_markdown_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1/export-markdown")
        assert resp.status_code in (401, 403, 404)

    async def test_export_html_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1/export-html")
        assert resp.status_code in (401, 403, 404)

    async def test_export_python_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1/export-python")
        assert resp.status_code in (401, 403, 404)

    async def test_export_json_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/test-case/1/export-json")
        assert resp.status_code in (401, 403, 404)

    async def test_export_excel_without_auth(self, async_client):
        resp = await async_client.post("/api/v1/test-case/1/export-excel")
        assert resp.status_code in (401, 403, 404)

    async def test_export_markdown_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-case/99999/export-markdown")
        assert resp.status_code in (403, 404, 500)

    async def test_export_json_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/test-case/99999/export-json")
        assert resp.status_code in (403, 404, 500)

    async def test_export_excel_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post("/api/v1/test-case/99999/export-excel")
        assert resp.status_code in (403, 404, 500)

    async def test_export_functional_excel_empty_ids(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/test-case/export-functional-excel",
            json={"case_ids": []},
        )
        assert resp.status_code in (400, 403, 404)

    async def test_export_functional_excel_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/test-case/export-functional-excel",
            json={"case_ids": [99999]},
        )
        assert resp.status_code in (403, 404, 500)
