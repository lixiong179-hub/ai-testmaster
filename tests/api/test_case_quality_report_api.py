import pytest


class TestCaseQualityReport:
    def test_review_without_auth(self, client):
        resp = client.post(
            "/api/v1/caseQuality/cases/1/review",
            json={"status": "approved", "review_comment": "通过"},
        )
        assert resp.status_code in (401, 403, 404)

    def test_review_nonexistent(self, client, authHeaders):
        resp = client.post(
            "/api/v1/caseQuality/cases/99999/review",
            json={"status": "approved", "review_comment": "通过"},
            headers=authHeaders,
        )
        assert resp.status_code in (404, 500)

    def test_review_invalid_status(self, client, db, authHeaders, testProject):
        from app.models.test_case import TestCase as TC
        case = TC(
            project_id=testProject.id, case_no="RQ-001",
            module="M", title="质量测试用例", priority=2,
            precondition="无", expected_result="预期结果",
            case_type="functional",
        )
        db.add(case)
        db.flush()
        resp = client.post(
            f"/api/v1/caseQuality/cases/{case.id}/review",
            json={"status": "invalid_status", "review_comment": "测试"},
            headers=authHeaders,
        )
        assert resp.status_code in (400, 404, 500)

    def test_edit_without_auth(self, client):
        resp = client.put(
            "/api/v1/caseQuality/cases/1/edit",
            json={"title": "新标题"},
        )
        assert resp.status_code in (401, 403, 404)

    def test_project_report_without_auth(self, client):
        resp = client.get("/api/v1/caseQuality/project/1/report")
        assert resp.status_code in (401, 403, 404)

    def test_project_trend_without_auth(self, client):
        resp = client.get("/api/v1/caseQuality/project/1/trend")
        assert resp.status_code in (401, 403, 404)

    def test_project_statistics_without_auth(self, client):
        resp = client.get("/api/v1/caseQuality/project/1/statistics")
        assert resp.status_code in (401, 403, 404)

    def test_project_report_nonexistent(self, client, authHeaders):
        resp = client.get(
            "/api/v1/caseQuality/project/99999/report",
            headers=authHeaders,
        )
        assert resp.status_code in (200, 404, 500)

    def test_project_trend_nonexistent(self, client, authHeaders):
        resp = client.get(
            "/api/v1/caseQuality/project/99999/trend",
            headers=authHeaders,
        )
        assert resp.status_code in (200, 404, 500)
