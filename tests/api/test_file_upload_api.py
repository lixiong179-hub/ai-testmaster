import io


class TestFileUploadEndpoint:
    async def test_upload_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/file/upload",
            data={"project_id": 1},
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code in (401, 403)

    async def test_upload_with_auth_no_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/file/upload",
            data={"project_id": 99999},
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert resp.status_code in (400, 403, 500)

    async def test_upload_no_file(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/file/upload",
            data={"project_id": async_test_project.id},
        )
        assert resp.status_code in (400, 422)

    async def test_submit_url_deprecated(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/file/submit-url",
            json={"url": "https://example.com", "project_id": 1, "file_type": "url"},
        )
        assert resp.status_code == 410

    async def test_update_sort_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/file/update-sort",
            json=[1, 2, 3],
        )
        assert resp.status_code in (401, 403)

    async def test_update_sort_empty_ids(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/file/update-sort",
            json=[],
        )
        assert resp.status_code in (400, 422)
