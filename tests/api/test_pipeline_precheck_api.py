"""Pipeline 场景4预检端点 async 测试。

覆盖 POST /api/v1/pipeline/scenario-4/precheck 端点的正常/异常/权限场景。
使用 tests/api/conftest.py 的 async_db / async_auth_client fixture。
"""
import pytest

from app.models.project import ProjectFile
from app.models.test_case import TestCase


async def _create_test_case(db, project_id: int, **kwargs) -> TestCase:
    """创建测试用例（新建实例不需要 enable_lifecycle_transition，guard 只检查 session.dirty）"""
    defaults = {
        "case_no": f"PRECHECK_{project_id}",
        "module": "测试模块",
        "title": "历史用例",
        "precondition": "无",
        "steps_json": [{"step": 1, "action": "操作", "expected_result": "结果"}],
        "expected_result": "预期结果",
        "priority": 2,
        "case_type": "ui_automation",
        "generate_status": 1,
        "lifecycle_status": "active",
    }
    defaults.update(kwargs)
    case = TestCase(project_id=project_id, **defaults)
    db.add(case)
    await db.flush()
    return case


class TestPipelinePrecheckAPI:
    async def test_without_auth(self, async_client) -> None:
        resp = await async_client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={"project_id": 1},
        )
        assert resp.status_code == 401

    async def test_nonexistent_project(self, async_auth_client) -> None:
        resp = await async_auth_client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={"project_id": 99999},
        )
        assert resp.status_code in (403, 404, 500)

    async def test_requirement_change_recommends_scenario_4(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        await _create_test_case(
            async_db, async_test_project.id,
            case_no="PRECHECK_REQ_001", title="历史登录用例",
        )
        req_file = ProjectFile(
            project_id=async_test_project.id,
            file_name="迭代需求.docx",
            file_type="docx",
            file_url="/tmp/req.docx",
            file_source="upload",
            content="新增登录验证码需求",
            is_active=True,
        )
        async_db.add(req_file)
        await async_db.flush()

        resp = await async_auth_client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={
                "project_id": async_test_project.id,
                "change_source": "requirement",
                "requirement_file_ids": [req_file.id],
            },
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["recommended_pipeline_scenario"] == 4
        assert data["context_quality"]["has_requirement"] is True
        assert data["can_run"] is True

    async def test_ui_change_without_requirement_recommends_scenario_5(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        await _create_test_case(
            async_db, async_test_project.id,
            case_no="PRECHECK_UI_001", title="历史设置用例",
        )
        await async_db.flush()

        resp = await async_auth_client.post(
            "/api/v1/pipeline/scenario-4/precheck",
            json={"project_id": async_test_project.id, "change_source": "ui_flow"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["recommended_pipeline_scenario"] == 5
        assert "没有已解析的 UI 页面" in data["blocking_reasons"]
