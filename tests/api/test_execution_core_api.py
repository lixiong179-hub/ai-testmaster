"""execution_core 端点 async 测试。

覆盖 /api/v1/execution/ 下的设备列表、开始/暂停/恢复/停止执行、
失败分析、快速验证端点。使用 tests/api/conftest.py 的 async fixture。
"""
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.enums import ExecStatus


async def _make_task(async_db, project_id, user_id, status=0):
    task = TestTask(
        project_id=project_id,
        task_name=f"执行任务_{id(async_db)}",
        executor_id=user_id,
        status=status,
        case_ids=[],
    )
    async_db.add(task)
    await async_db.flush()
    return task


async def _make_case(async_db, project_id):
    case = TestCase(
        project_id=project_id,
        case_no=f"EXEC-{id(async_db)}",
        module="执行模块",
        title="执行测试用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI",
    )
    async_db.add(case)
    await async_db.flush()
    return case


async def _make_result(async_db, task_id, project_id, case_id, case_no, exec_status=ExecStatus.FAILED, error_msg="", ai_analysis=""):
    result = TestResult(
        task_id=task_id,
        project_id=project_id,
        case_id=case_id,
        case_no=case_no,
        exec_status=int(exec_status),
        error_msg=error_msg,
        ai_analysis=ai_analysis,
    )
    async_db.add(result)
    await async_db.flush()
    return result


class TestListDevicesAPI:

    async def test_devices_endpoint(self, async_auth_client):
        response = await async_auth_client.get("/api/v1/execution/devices")
        assert response.status_code == 200

    async def test_devices_unauthenticated(self, async_client):
        response = await async_client.get("/api/v1/execution/devices")
        assert response.status_code == 401


class TestStartExecutionAPI:

    async def test_start_nonexistent_task(self, async_auth_client):
        response = await async_auth_client.post(
            "/api/v1/execution/99999/start",
        )
        assert response.status_code == 404

    async def test_start_unauthenticated(self, async_client):
        response = await async_client.post("/api/v1/execution/1/start")
        assert response.status_code == 401


class TestPauseExecutionAPI:

    async def test_pause_nonexistent_task(self, async_auth_client):
        response = await async_auth_client.post("/api/v1/execution/99999/pause")
        assert response.status_code == 404

    async def test_pause_unauthenticated(self, async_client):
        response = await async_client.post("/api/v1/execution/1/pause")
        assert response.status_code == 401


class TestResumeExecutionAPI:

    async def test_resume_nonexistent_task(self, async_auth_client):
        response = await async_auth_client.post("/api/v1/execution/99999/resume")
        assert response.status_code == 404

    async def test_resume_unauthenticated(self, async_client):
        response = await async_client.post("/api/v1/execution/1/resume")
        assert response.status_code == 401


class TestStopExecutionAPI:

    async def test_stop_nonexistent_task(self, async_auth_client):
        response = await async_auth_client.post("/api/v1/execution/99999/stop")
        assert response.status_code == 404

    async def test_stop_unauthenticated(self, async_client):
        response = await async_client.post("/api/v1/execution/1/stop")
        assert response.status_code == 401


class TestAnalyzeFailureAPI:

    async def test_analyze_nonexistent_result(self, async_auth_client):
        response = await async_auth_client.post(
            "/api/v1/execution/results/99999/analyze-failure",
        )
        assert response.status_code == 404

    async def test_analyze_non_failed_result(self, async_auth_client, async_db, async_test_project, async_test_user):
        task = await _make_task(async_db, async_test_project.id, async_test_user.id)
        case = await _make_case(async_db, async_test_project.id)
        result = await _make_result(async_db, task.id, async_test_project.id, case.id, case.case_no, exec_status=ExecStatus.PASSED)
        response = await async_auth_client.post(
            f"/api/v1/execution/results/{result.id}/analyze-failure",
        )
        assert response.status_code == 400

    async def test_analyze_failed_result(self, async_auth_client, async_db, async_test_project, async_test_user):
        task = await _make_task(async_db, async_test_project.id, async_test_user.id)
        case = await _make_case(async_db, async_test_project.id)
        result = await _make_result(async_db, task.id, async_test_project.id, case.id, case.case_no, exec_status=ExecStatus.FAILED, error_msg="元素未找到")
        response = await async_auth_client.post(
            f"/api/v1/execution/results/{result.id}/analyze-failure",
        )
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        data = response.json()["data"]
        assert "suggested_type" in data
        assert "case_issue_indicators" in data
        assert "bug_issue_indicators" in data

    async def test_analyze_with_ai_analysis(self, async_auth_client, async_db, async_test_project, async_test_user):
        task = await _make_task(async_db, async_test_project.id, async_test_user.id)
        case = await _make_case(async_db, async_test_project.id)
        result = await _make_result(
            async_db, task.id, async_test_project.id, case.id, case.case_no,
            exec_status=ExecStatus.FAILED,
            error_msg="功能缺陷", ai_analysis="产品问题需要修复bug"
        )
        response = await async_auth_client.post(
            f"/api/v1/execution/results/{result.id}/analyze-failure",
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["suggested_type"] in ("product_bug", "case_issue", "needs_review")

    async def test_analyze_unauthenticated(self, async_client, async_db, async_test_project, async_test_user):
        task = await _make_task(async_db, async_test_project.id, async_test_user.id)
        case = await _make_case(async_db, async_test_project.id)
        result = await _make_result(async_db, task.id, async_test_project.id, case.id, case.case_no, exec_status=ExecStatus.FAILED)
        response = await async_client.post(f"/api/v1/execution/results/{result.id}/analyze-failure")
        assert response.status_code == 401


class TestQuickVerifyAPI:

    async def test_quick_verify_nonexistent_case(self, async_auth_client):
        response = await async_auth_client.post(
            "/api/v1/execution/quick-verify",
            json={"case_id": 99999, "step_indices": []},
        )
        assert response.status_code in (404, 500)

    async def test_quick_verify_unauthenticated(self, async_client, async_db, async_test_project):
        case = await _make_case(async_db, async_test_project.id)
        response = await async_client.post(
            "/api/v1/execution/quick-verify",
            json={"case_id": case.id, "step_indices": []},
        )
        assert response.status_code == 401
