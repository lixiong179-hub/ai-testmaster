import pytest

from app.models.project import ProjectFile
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition


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

    def test_requirement_change_recommends_scenario_4(self, client, authHeaders, db, testProject):
        enable_lifecycle_transition()
        db.add(TestCase(
            project_id=testProject.id,
            case_no="PRECHECK_REQ_001",
            module="登录",
            title="历史登录用例",
            precondition="已打开登录页",
            steps_json=[{"step": 1, "action": "输入账号", "expected_result": "可输入"}],
            expected_result="登录成功",
            priority=2,
            case_type="ui_automation",
            generate_status=1,
            lifecycle_status="active",
        ))
        disable_lifecycle_transition()
        req_file = ProjectFile(
            project_id=testProject.id,
            file_name="迭代需求.docx",
            file_type="docx",
            file_url="/tmp/req.docx",
            file_source="upload",
            content="新增登录验证码需求",
            is_active=True,
        )
        db.add(req_file)
        db.flush()

        resp = client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={
                "project_id": testProject.id,
                "change_source": "requirement",
                "requirement_file_ids": [req_file.id],
            },
            headers=authHeaders,
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["recommended_pipeline_scenario"] == 4
        assert data["context_quality"]["has_requirement"] is True

    def test_ui_change_without_requirement_recommends_scenario_5(self, client, authHeaders, db, testProject):
        enable_lifecycle_transition()
        db.add(TestCase(
            project_id=testProject.id,
            case_no="PRECHECK_UI_001",
            module="设置",
            title="历史设置用例",
            precondition="已登录",
            steps_json=[{"step": 1, "action": "进入设置", "expected_result": "显示设置页"}],
            expected_result="显示设置页",
            priority=2,
            case_type="ui_automation",
            generate_status=1,
            lifecycle_status="active",
        ))
        disable_lifecycle_transition()
        db.flush()

        resp = client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={"project_id": testProject.id, "change_source": "ui_flow"},
            headers=authHeaders,
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["recommended_pipeline_scenario"] == 5
        assert "没有已解析的 UI 页面" in data["blocking_reasons"]
