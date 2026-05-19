import pytest


class TestWorkflowEndpoints:
    def test_technical_view_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/technical-view")
        assert resp.status_code in (401, 403, 404)

    def test_business_view_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/business-view")
        assert resp.status_code in (401, 403, 404)

    def test_technical_view_nonexistent(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/technical-view",
            headers=authHeaders,
        )
        assert resp.status_code in (403, 404, 500)

    def test_business_view_nonexistent(self, client, authHeaders):
        resp = client.get(
            "/api/v1/testCase/99999/business-view",
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)

    def test_workflow_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/workflow")
        assert resp.status_code in (401, 403, 404)

    def test_workflow_transition_without_auth(self, client):
        resp = client.post(
            "/api/v1/testCase/1/workflow/transition",
            json={"status": "active"},
        )
        assert resp.status_code in (401, 403, 404)

    def test_correction_status_without_auth(self, client):
        resp = client.get("/api/v1/testCase/1/correction-status")
        assert resp.status_code in (401, 403, 404)

    def test_start_correction_without_auth(self, client):
        resp = client.post("/api/v1/testCase/1/start-correction")
        assert resp.status_code in (401, 403, 404)

    def test_submit_verification_without_auth(self, client):
        resp = client.post("/api/v1/testCase/1/submit-verification")
        assert resp.status_code in (401, 403, 404)

    def test_workflow_transition_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/testCase/99999/workflow/transition",
            json={"status": "active"},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)

    def test_start_correction_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/testCase/99999/start-correction",
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)
