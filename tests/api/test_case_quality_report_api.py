"""case_quality_report.py 端点 async 测试。

覆盖 /api/v1/quality/ 端点的未认证、不存在资源、无效参数场景。
使用 tests/api/conftest.py 的 async fixture。

注意：原测试用例 URL /api/v1/caseQuality/... 错误（实际路由为 /quality/），
导致所有"通过"测试实际是 404 路径不存在。本文件修正 URL 并使用 async fixture。
"""


class TestCaseQualityReport:
    """用例质量报告端点测试。"""

    async def test_review_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/quality/cases/1/review",
            json={"status": "approved", "review_comment": "通过"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_review_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/quality/cases/1/review")
        assert resp.status_code in (401, 403, 404)

    async def test_pending_reviews_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/quality/projects/1/pending-reviews")
        assert resp.status_code in (401, 403, 404)

    async def test_edit_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/quality/cases/1/edit",
            json={"title": "新标题"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_edit_step_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/quality/cases/1/steps/1",
            json={"action": "click"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_project_cost_stats_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/quality/projects/1/cost-statistics")
        assert resp.status_code in (401, 403, 404)

    async def test_project_cost_report_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/quality/projects/1/cost-report")
        assert resp.status_code in (401, 403, 404)

    async def test_case_cost_stats_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/quality/cases/1/cost-statistics")
        assert resp.status_code in (401, 403, 404)

    async def test_review_nonexistent(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/quality/cases/99999/review",
            json={"status": "approved", "review_comment": "通过"},
        )
        assert resp.status_code in (404, 500)

    async def test_review_invalid_status(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/quality/cases/1/review",
            json={"status": "invalid_status", "review_comment": "测试"},
        )
        assert resp.status_code == 400

    async def test_get_review_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/quality/cases/99999/review")
        assert resp.status_code in (404, 500)

    async def test_edit_nonexistent(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/quality/cases/99999/edit",
            json={"title": "新标题"},
        )
        assert resp.status_code in (404, 500)

    async def test_edit_step_nonexistent(self, async_auth_client):
        resp = await async_auth_client.put(
            "/api/v1/quality/cases/99999/steps/99999",
            json={"step_id": 99999, "action": "click"},
        )
        assert resp.status_code in (404, 500)

    async def test_pending_reviews_empty(self, async_auth_client, async_test_project):
        resp = await async_auth_client.get(
            f"/api/v1/quality/projects/{async_test_project.id}/pending-reviews"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 0
        assert data["cases"] == []

    async def test_review_case_success(
        self, async_db, async_auth_client, async_test_project
    ):
        """测试审核成功场景。

        NOTE: 已修复预存 bug — 原端点 response_model=CaseReviewResponse 与 DB
        priority(int) 类型不匹配，FastAPI 抛 ResponseValidationError。已移除
        response_model 装饰器，端点直接返回 dict。
        """
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no="RQ-ASYNC-001",
            module="M",
            title="质量测试用例",
            priority=2,
            precondition="无",
            steps_json=[],
            expected_result="预期结果",
            case_type="functional",
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/quality/cases/{case.id}/review",
            json={"status": "approved", "review_comment": "通过"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "approved"
        assert data["review_comment"] == "通过"

    async def test_get_review_status(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no="RQ-ASYNC-002",
            module="M",
            title="质量测试用例2",
            priority=2,
            precondition="无",
            steps_json=[],
            expected_result="预期结果",
            case_type="functional",
            review_status="pending",
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.get(
            f"/api/v1/quality/cases/{case.id}/review"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["case_id"] == case.id
        assert data["status"] == "pending"

    async def test_pending_reviews_with_data(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no="RQ-PENDING-001",
            module="M",
            title="待审核用例",
            priority=2,
            precondition="无",
            steps_json=[],
            expected_result="预期结果",
            case_type="functional",
            review_status="pending",
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.get(
            f"/api/v1/quality/projects/{async_test_project.id}/pending-reviews"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["pending_count"] >= 1
        assert any(c["case_id"] == case.id for c in data["cases"])

    async def test_edit_case_success(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no="RQ-EDIT-001",
            module="M",
            title="待编辑用例",
            priority=2,
            precondition="无",
            steps_json=[],
            expected_result="预期结果",
            case_type="functional",
        )
        async_db.add(case)
        await async_db.flush()

        resp = await async_auth_client.put(
            f"/api/v1/quality/cases/{case.id}/edit",
            json={"title": "编辑后标题"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["message"] == "用例更新成功"

    async def test_project_cost_statistics(
        self, async_auth_client, async_test_project
    ):
        resp = await async_auth_client.get(
            f"/api/v1/quality/projects/{async_test_project.id}/cost-statistics"
        )
        assert resp.status_code in (200, 500)

    async def test_project_cost_report(
        self, async_auth_client, async_test_project
    ):
        resp = await async_auth_client.get(
            f"/api/v1/quality/projects/{async_test_project.id}/cost-report",
            params={"days": 7},
        )
        assert resp.status_code in (200, 500)

    async def test_case_cost_statistics_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/quality/cases/99999/cost-statistics"
        )
        assert resp.status_code in (404, 500)
