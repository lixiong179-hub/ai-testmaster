import pytest


class TestExportMarkdown:
    def test_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/export-markdown")
        assert resp.status_code in (401, 403, 404)

    def test_nonexistent_case(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/export-markdown",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)


class TestExportHtml:
    def test_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/export-html")
        assert resp.status_code in (401, 403, 404)

    def test_nonexistent_case(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/export-html",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)


class TestExportPython:
    def test_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/export-python")
        assert resp.status_code in (401, 403, 404)

    def test_nonexistent_case(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/export-python",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)


class TestExportJson:
    def test_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/export-json")
        assert resp.status_code in (401, 403, 404)

    def test_nonexistent_case(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/export-json",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)


class TestExportExcel:
    def test_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/export-excel")
        assert resp.status_code in (401, 403, 404, 405)

    def test_nonexistent_case(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/export-excel",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500, 405)


class TestFunctionalExcelExport:
    def test_without_auth(self, client):
        resp = client.post(
            "/api/v1/testCase/functional-excel-export",
            json={"case_ids": [1, 2]},
        )
        assert resp.status_code in (401, 403, 404, 405)

    def test_empty_case_ids(self, client, authHeaders):
        resp = client.post(
            "/api/v1/testCase/functional-excel-export",
            json={"case_ids": []},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 422, 405)

    def test_nonexistent_cases(self, client, authHeaders):
        resp = client.post(
            "/api/v1/testCase/functional-excel-export",
            json={"case_ids": [99998, 99999]},
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500, 405)
