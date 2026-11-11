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


class TestReviewInboxByIteration:
    """GET /review/by-iteration/{iteration_id}

    前端「查看评审」「前往评审 Inbox」依赖该接口定位最新一条评审；
    此前前端已有调用但后端未实现（接线缺口），本组测试锁定契约。
    """

    async def test_list_by_iteration_empty(self, async_auth_client):
        """迭代下无评审时返回空列表（而非 404）"""
        resp = await async_auth_client.get(
            "/api/v1/review/by-iteration/99999",
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["reviews"] == []
        assert data["total"] == 0

    async def test_list_by_iteration_status_filter(self, async_auth_client):
        """status 过滤参数被接受"""
        resp = await async_auth_client.get(
            "/api/v1/review/by-iteration/99999",
            params={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["reviews"] == []

    async def test_list_by_iteration_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/review/by-iteration/1")
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
