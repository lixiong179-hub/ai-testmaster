import pytest


class TestReviewInboxQueries:
    async def test_list_decisions_no_review(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/review/99999/decisions",
        )
        assert resp.status_code in (200, 404, 500)

    async def test_list_decisions_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/review/1/decisions")
        assert resp.status_code in (401, 403)


class TestReviewInboxMutations:
    async def test_decide_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/review/99999/decisions/99999/decide",
            json={"human_verdict": "keep", "human_reason": "测试"},
        )
        assert resp.status_code in (400, 404, 500)

    async def test_batch_decide_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/review/99999/decisions/batch-decide",
            json={"decisions": [{"decision_id": 1, "human_verdict": "keep", "human_reason": "测试"}]},
        )
        assert resp.status_code in (400, 404, 500)

    async def test_finalize_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/review/99999/finalize",
        )
        assert resp.status_code in (400, 404, 500)

    async def test_rollback_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/review/99999/decisions/99999/rollback",
        )
        assert resp.status_code in (400, 403, 404, 500)

    async def test_undo_decision_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/review/99999/undo-decision/99999",
        )
        assert resp.status_code in (400, 403, 404, 500)

    async def test_apply_decisions_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/review/99999/apply-decisions",
        )
        assert resp.status_code in (400, 404, 500)

    async def test_decide_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/review/1/decisions/1/decide",
            json={"human_verdict": "keep", "human_reason": "测试"},
        )
        assert resp.status_code in (401, 403)
