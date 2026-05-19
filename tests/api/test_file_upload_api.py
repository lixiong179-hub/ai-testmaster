import io
import pytest


class TestFileUploadEndpoint:
    def test_upload_without_auth(self, client):
        resp = client.post(
            "/api/v1/file/upload",
            data={"project_id": 1},
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code in (401, 403)

    def test_upload_with_auth_no_project(self, client, authHeaders):
        resp = client.post(
            "/api/v1/file/upload",
            data={"project_id": 99999},
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 403, 500)

    def test_upload_no_file(self, client, authHeaders, testProject):
        resp = client.post(
            "/api/v1/file/upload",
            data={"project_id": testProject.id},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 422)

    def test_submit_url_deprecated(self, client, authHeaders):
        resp = client.post(
            "/api/v1/file/submit-url",
            json={"url": "https://example.com", "project_id": 1, "file_type": "url"},
            headers=authHeaders,
        )
        assert resp.status_code == 410

    def test_update_sort_without_auth(self, client):
        resp = client.post(
            "/api/v1/file/update-sort",
            json=[1, 2, 3],
        )
        assert resp.status_code in (401, 403)

    def test_update_sort_empty_ids(self, client, authHeaders):
        resp = client.post(
            "/api/v1/file/update-sort",
            json=[],
            headers=authHeaders,
        )
        assert resp.status_code in (400, 422)
