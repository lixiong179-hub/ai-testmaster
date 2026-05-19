import pytest


class TestPipelinePrecheckAPI:
    def test_without_auth(self, client):
        resp = client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={"project_id": 1},
        )
        assert resp.status_code in (401, 403, 404)

    def test_nonexistent_project(self, client, authHeaders):
        resp = client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={"project_id": 99999},
            headers=authHeaders,
        )
        assert resp.status_code in (403, 404, 500)
