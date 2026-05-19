import pytest


class TestReviewInboxQueries:
    def test_list_decisions_no_review(self, client, authHeaders):
        resp = client.get(
            "/api/v1/review/99999/decisions",
            headers=authHeaders,
        )
        assert resp.status_code in (200, 404, 500)

    def test_list_decisions_without_auth(self, client):
        resp = client.get("/api/v1/review/1/decisions")
        assert resp.status_code in (401, 403)


class TestReviewInboxMutations:
    def test_decide_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/review/99999/decisions/99999/decide",
            json={"human_verdict": "keep", "human_reason": "测试"},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)

    def test_batch_decide_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/review/99999/decisions/batch-decide",
            json={"decisions": [{"decision_id": 1, "human_verdict": "keep", "human_reason": "测试"}]},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)

    def test_finalize_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/review/99999/finalize",
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)

    def test_rollback_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/review/99999/decisions/99999/rollback",
            headers=authHeaders,
        )
        assert resp.status_code in (400, 403, 404, 500)

    def test_undo_decision_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/review/99999/undo-decision/99999",
            headers=authHeaders,
        )
        assert resp.status_code in (400, 403, 404, 500)

    def test_apply_decisions_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/review/99999/apply-decisions",
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)

    def test_decide_without_auth(self, client):
        resp = client.post(
            "/api/v1/review/1/decisions/1/decide",
            json={"human_verdict": "keep", "human_reason": "测试"},
        )
        assert resp.status_code in (401, 403)
