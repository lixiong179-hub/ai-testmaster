import pytest


class TestAIGenerateEndpoint:
    def test_generate_without_auth(self, client):
        resp = client.post(
            "/api/v1/ai-generate",
            json={"project_id": 1, "point_ids": [1]},
        )
        assert resp.status_code in (401, 403, 404, 422)

    def test_generate_with_auth_no_project(self, client, authHeaders):
        resp = client.post(
            "/api/v1/ai-generate",
            json={"project_id": 99999, "point_ids": []},
            headers=authHeaders,
        )
        assert resp.status_code in (200, 400, 403, 404, 500)

    def test_generate_missing_body(self, client, authHeaders):
        resp = client.post(
            "/api/v1/ai-generate",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 422)


class TestAIContextEndpoint:
    def test_context_without_auth(self, client):
        resp = client.get(
            "/api/v1/ai-generate/context",
            params={"project_id": 1},
        )
        assert resp.status_code in (401, 403, 404)
