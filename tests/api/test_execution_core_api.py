import pytest

from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.enums import ExecStatus, LocatorStatus
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def exec_user(db):
    user = User(username="exec_api_user", email="exec_api@test.com", password_hash="hash", is_active=True)
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    try:
        db.query(TestResult).filter(
            TestResult.case_id.in_(
                db.query(TestCase.id).filter(
                    TestCase.project_id.in_(
                        db.query(Project.id).filter(Project.user_id == user.id)
                    )
                )
            )
        ).delete(synchronize_session=False)
        db.query(TestTask).filter(
            TestTask.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(TestCase).filter(
            TestCase.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture
def exec_project(db, exec_user):
    project = Project(name="exec_api_project", user_id=exec_user.id, description="exec test", status=1, project_type="web")
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_task(db, project_id, user_id, status=0):
    task = TestTask(
        project_id=project_id,
        task_name=f"执行任务_{id(db)}",
        executor_id=user_id,
        status=status,
    )
    db.add(task)
    db.flush()
    db.refresh(task)
    return task


def _make_case(db, project_id):
    case = TestCase(
        project_id=project_id,
        case_no=f"EXEC-{id(db)}",
        module="执行模块",
        title="执行测试用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI",
    )
    db.add(case)
    db.flush()
    db.refresh(case)
    return case


def _make_result(db, task_id, project_id, case_id, case_no, exec_status=ExecStatus.FAILED, error_msg="", ai_analysis=""):
    result = TestResult(
        task_id=task_id,
        project_id=project_id,
        case_id=case_id,
        case_no=case_no,
        exec_status=int(exec_status),
        error_msg=error_msg,
        ai_analysis=ai_analysis,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


class TestListDevicesAPI:

    def test_devices_endpoint(self, client, authHeaders):
        response = client.get("/api/v1/execution/devices", headers=authHeaders)
        assert response.status_code == 200

    def test_devices_unauthenticated(self, client):
        response = client.get("/api/v1/execution/devices")
        assert response.status_code == 401


class TestStartExecutionAPI:

    def test_start_nonexistent_task(self, client, authHeaders):
        response = client.post(
            "/api/v1/execution/99999/start",
            headers=authHeaders,
        )
        assert response.status_code == 404

    def test_start_unauthenticated(self, client):
        response = client.post("/api/v1/execution/1/start")
        assert response.status_code == 401


class TestPauseExecutionAPI:

    def test_pause_nonexistent_task(self, client, authHeaders):
        response = client.post("/api/v1/execution/99999/pause", headers=authHeaders)
        assert response.status_code == 404

    def test_pause_unauthenticated(self, client):
        response = client.post("/api/v1/execution/1/pause")
        assert response.status_code == 401


class TestResumeExecutionAPI:

    def test_resume_nonexistent_task(self, client, authHeaders):
        response = client.post("/api/v1/execution/99999/resume", headers=authHeaders)
        assert response.status_code == 404

    def test_resume_unauthenticated(self, client):
        response = client.post("/api/v1/execution/1/resume")
        assert response.status_code == 401


class TestStopExecutionAPI:

    def test_stop_nonexistent_task(self, client, authHeaders):
        response = client.post("/api/v1/execution/99999/stop", headers=authHeaders)
        assert response.status_code == 404

    def test_stop_unauthenticated(self, client):
        response = client.post("/api/v1/execution/1/stop")
        assert response.status_code == 401


class TestAnalyzeFailureAPI:

    def test_analyze_nonexistent_result(self, client, authHeaders):
        response = client.post(
            "/api/v1/execution/results/99999/analyze-failure",
            headers=authHeaders,
        )
        assert response.status_code == 404

    def test_analyze_non_failed_result(self, client, authHeaders, db, exec_project, exec_user):
        task = _make_task(db, exec_project.id, exec_user.id)
        case = _make_case(db, exec_project.id)
        result = _make_result(db, task.id, exec_project.id, case.id, case.case_no, exec_status=ExecStatus.PASSED)
        response = client.post(
            f"/api/v1/execution/results/{result.id}/analyze-failure",
            headers=authHeaders,
        )
        assert response.status_code == 400

    def test_analyze_failed_result(self, client, authHeaders, db, exec_project, exec_user):
        task = _make_task(db, exec_project.id, exec_user.id)
        case = _make_case(db, exec_project.id)
        result = _make_result(db, task.id, exec_project.id, case.id, case.case_no, exec_status=ExecStatus.FAILED, error_msg="元素未找到")
        response = client.post(
            f"/api/v1/execution/results/{result.id}/analyze-failure",
            headers=authHeaders,
        )
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        data = response.json()["data"]
        assert "suggested_type" in data
        assert "case_issue_indicators" in data
        assert "bug_issue_indicators" in data

    def test_analyze_with_ai_analysis(self, client, authHeaders, db, exec_project, exec_user):
        task = _make_task(db, exec_project.id, exec_user.id)
        case = _make_case(db, exec_project.id)
        result = _make_result(
            db, task.id, exec_project.id, case.id, case.case_no,
            exec_status=ExecStatus.FAILED,
            error_msg="功能缺陷", ai_analysis="产品问题需要修复bug"
        )
        response = client.post(
            f"/api/v1/execution/results/{result.id}/analyze-failure",
            headers=authHeaders,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["suggested_type"] in ("product_bug", "case_issue", "needs_review")

    def test_analyze_unauthenticated(self, client, db, exec_project, exec_user):
        task = _make_task(db, exec_project.id, exec_user.id)
        case = _make_case(db, exec_project.id)
        result = _make_result(db, task.id, exec_project.id, case.id, case.case_no, exec_status=ExecStatus.FAILED)
        response = client.post(f"/api/v1/execution/results/{result.id}/analyze-failure")
        assert response.status_code == 401


class TestQuickVerifyAPI:

    def test_quick_verify_nonexistent_case(self, client, authHeaders):
        response = client.post(
            "/api/v1/execution/quick-verify",
            json={"case_id": 99999, "step_indices": []},
            headers=authHeaders,
        )
        assert response.status_code in (404, 500)

    def test_quick_verify_unauthenticated(self, client, db, exec_project):
        case = _make_case(db, exec_project.id)
        response = client.post(
            "/api/v1/execution/quick-verify",
            json={"case_id": case.id, "step_indices": []},
        )
        assert response.status_code == 401
