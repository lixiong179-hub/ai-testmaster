"""Pipeline 取消运行 API 测试

覆盖范围:
    - admin 可取消任意运行
    - qa_lead 可取消自己发起的运行
    - qa_lead 不可取消他人发起的运行
    - 普通用户仅可取消自己发起的运行
    - running / waiting_for_user / pending 状态可取消
    - completed / cancelled / failed 状态返回 409
    - 取消后审计日志写入
    - 取消后 Runner 不再执行后续 Step
    - 不存在的 run_id 返回 404
    - 无权限用户返回 403

使用真实 MySQL、HTTP TestClient + JWT。
"""
import hashlib
import pytest

from app.models.iteration import Iteration
from app.models.pipeline import PipelineRun
from app.models.enums import PipelineRunStatus
from app.services.pipeline_permission_service import (
    init_pipeline_roles,
    assign_pipeline_role,
    check_pipeline_permission,
)
from app.utils.jwt_utils import create_access_token, get_password_hash


# ── Helpers ───────────────────────────────────────────────────────────


def _make_user(db, username: str, email: str, is_superuser: bool = False):
    """创建测试用户。"""
    from app.models.user import User

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    return user


def _make_project(db, user_id: int, name: str):
    """创建测试项目（属于指定用户）。"""
    from app.models.project import Project

    project = Project(
        name=name,
        user_id=user_id,
        description="cancel test project",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


def _make_iteration(db, project_id: int, name: str = "cancel_iter"):
    """创建测试迭代。"""
    iteration = Iteration(
        project_id=project_id,
        name=name,
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


def _make_run(db, iteration_id: int, status: str, triggered_by: int = None) -> PipelineRun:
    """创建指定状态的 PipelineRun 记录。"""
    unique_hash = hashlib.sha256(
        f"cancel-test-{iteration_id}-{status}".encode(),
    ).hexdigest()
    run = PipelineRun(
        iteration_id=iteration_id,
        input_hash=unique_hash,
        pipeline_version="1.0",
        status=status,
        triggered_by=triggered_by,
    )
    db.add(run)
    db.flush()
    return run


def _auth_headers(user_id: int, username: str) -> dict:
    """生成 JWT 认证头。"""
    token = create_access_token({"sub": str(user_id), "username": username})
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _init_pipeline_roles(db):
    """每个测试前确保 Pipeline 角色和权限已初始化。"""
    init_pipeline_roles(db)
    db.flush()


@pytest.fixture
def admin_setup(db):
    """admin 用户 + 其拥有的项目 + 迭代 + pipeline admin 角色。"""
    admin = _make_user(db, "cancel_admin", "cancel_admin@test.com")
    project = _make_project(db, admin.id, "cancel_admin_proj")
    iteration = _make_iteration(db, project.id, "cancel_admin_iter")
    assign_pipeline_role(db, admin.id, "admin", project.id)
    db.flush()
    return {
        "user": admin,
        "project": project,
        "iteration": iteration,
        "headers": _auth_headers(admin.id, admin.username),
    }


@pytest.fixture
def qa_lead_setup(db):
    """qa_lead 用户 + 其拥有的项目 + 迭代 + qa_lead 角色。"""
    qa_lead = _make_user(db, "cancel_qa_lead", "cancel_qa_lead@test.com")
    project = _make_project(db, qa_lead.id, "cancel_qa_lead_proj")
    iteration = _make_iteration(db, project.id, "cancel_qa_lead_iter")
    assign_pipeline_role(db, qa_lead.id, "qa_lead", project.id)
    db.flush()
    return {
        "user": qa_lead,
        "project": project,
        "iteration": iteration,
        "headers": _auth_headers(qa_lead.id, qa_lead.username),
    }


@pytest.fixture
def other_qa_lead_setup(db):
    """另一个 qa_lead 用户（不同项目），用于测试跨用户取消限制。"""
    other = _make_user(db, "cancel_other_lead", "cancel_other_lead@test.com")
    project = _make_project(db, other.id, "cancel_other_lead_proj")
    iteration = _make_iteration(db, project.id, "cancel_other_lead_iter")
    assign_pipeline_role(db, other.id, "qa_lead", project.id)
    db.flush()
    return {
        "user": other,
        "project": project,
        "iteration": iteration,
        "headers": _auth_headers(other.id, other.username),
    }


@pytest.fixture
def qa_engineer_setup(db):
    """qa_engineer 用户（无 cancel 权限）。"""
    engineer = _make_user(db, "cancel_engineer", "cancel_engineer@test.com")
    project = _make_project(db, engineer.id, "cancel_engineer_proj")
    iteration = _make_iteration(db, project.id, "cancel_engineer_iter")
    assign_pipeline_role(db, engineer.id, "qa_engineer", project.id)
    db.flush()
    return {
        "user": engineer,
        "project": project,
        "iteration": iteration,
        "headers": _auth_headers(engineer.id, engineer.username),
    }


# ── 权限测试 ──────────────────────────────────────────────────────────


class TestCancelPermission:
    """Pipeline 取消权限校验。"""

    def test_admin_can_cancel_any_run(self, client, db, admin_setup):
        """admin 拥有 pipeline:cancel:all，可取消任意运行（包括他人发起的）。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "running",
            triggered_by=9999,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_qa_lead_can_cancel_own_run(self, client, db, qa_lead_setup):
        """qa_lead 拥有 pipeline:cancel:own，可取消自己发起的运行。"""
        run = _make_run(
            db, qa_lead_setup["iteration"].id, "running",
            triggered_by=qa_lead_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=qa_lead_setup["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_qa_lead_cannot_cancel_others_run(
        self, client, db, qa_lead_setup, other_qa_lead_setup,
    ):
        """qa_lead 的 cancel:own 不允许取消他人发起的运行。

        将 other_qa_lead 发起的运行放在 qa_lead 的项目迭代下，
        qa_lead 仍有项目访问权但 triggered_by 不是自己，应返回 403。
        """
        # 在 qa_lead 的项目下创建 other_qa_lead 发起的运行
        run = _make_run(
            db, qa_lead_setup["iteration"].id, "running",
            triggered_by=other_qa_lead_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=qa_lead_setup["headers"],
        )
        assert resp.status_code == 403

    def test_qa_engineer_cannot_cancel(self, client, db, qa_engineer_setup):
        """qa_engineer 无 cancel 权限，不可取消任何运行（即使自己发起的）。"""
        run = _make_run(
            db, qa_engineer_setup["iteration"].id, "running",
            triggered_by=qa_engineer_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=qa_engineer_setup["headers"],
        )
        assert resp.status_code == 403

    def test_viewer_cannot_cancel(self, client, db, qa_lead_setup):
        """viewer 无 cancel 权限。"""
        viewer = _make_user(db, "cancel_viewer", "cancel_viewer@test.com")
        assign_pipeline_role(db, viewer.id, "viewer", qa_lead_setup["project"].id)
        db.flush()

        run = _make_run(
            db, qa_lead_setup["iteration"].id, "running",
            triggered_by=viewer.id,
        )
        headers = _auth_headers(viewer.id, viewer.username)
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=headers,
        )
        assert resp.status_code == 403


# ── 状态测试 ──────────────────────────────────────────────────────────


class TestCancelStatusValidation:
    """不同状态下取消的合法性校验。"""

    def test_cancel_running_status(self, client, db, admin_setup):
        """running 状态可取消。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "running",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_cancel_waiting_for_user_status(self, client, db, admin_setup):
        """waiting_for_user 状态可取消。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "waiting_for_user",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_cancel_pending_status(self, client, db, admin_setup):
        """pending 状态可取消。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "pending",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "cancelled"

    def test_cancel_completed_returns_409(self, client, db, admin_setup):
        """completed 状态不可取消，返回 409。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "completed",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 409
        assert "completed" in resp.json()["message"]

    def test_cancel_already_cancelled_returns_409(self, client, db, admin_setup):
        """cancelled 状态不可重复取消，返回 409。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "cancelled",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 409
        assert "cancelled" in resp.json()["message"]

    def test_cancel_failed_returns_409(self, client, db, admin_setup):
        """failed 状态不可取消，返回 409。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "failed",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 409
        assert "failed" in resp.json()["message"]


# ── 404 测试 ──────────────────────────────────────────────────────────


class TestCancelNotFound:
    """不存在的 run_id 返回 404。"""

    def test_cancel_nonexistent_run(self, client, db, admin_setup):
        resp = client.post(
            "/api/v1/pipeline/999999/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 404


# ── 审计日志测试 ──────────────────────────────────────────────────────


class TestCancelAuditLog:
    """取消后审计日志写入验证。"""

    def test_cancel_creates_audit_log(self, client, db, admin_setup):
        """取消操作应写入 pipeline_cancel 审计日志。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "running",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200

        from app.models.audit_log import AuditLog

        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "pipeline_cancel",
                AuditLog.target_id == run.id,
            )
            .first()
        )
        assert audit is not None
        assert audit.actor_id == admin_setup["user"].id
        assert audit.target_kind == "pipeline_run"
        assert audit.run_id == run.id
        assert audit.iteration_id == admin_setup["iteration"].id
        assert audit.detail["from_status"] == "running"
        assert audit.detail["to_status"] == "cancelled"


# ── Runner 取消检查测试 ──────────────────────────────────────────────


class TestRunnerCancelCheck:
    """Runner 在 Step 间检测 cancelled 状态后停止执行。"""

    def test_runner_stops_on_cancelled_status(self, db, admin_setup):
        """模拟 Runner 在 Step 循环中检测到 cancelled 状态后立即停止。"""
        from app.pipelines.runner import PipelineRunner
        from app.pipelines.base import PipelineStep, StepResult
        from app.pipelines.context import PipelineContext
        from app.services import pipeline_service
        from unittest.mock import patch

        executed_steps: list[str] = []

        class StepA(PipelineStep):
            name = "step_a"
            version = "1.0"

            def should_run(self, ctx):
                return True

            def execute(self, ctx):
                executed_steps.append("step_a")
                return StepResult(
                    success=True, artifact_kind="a",
                    artifact_payload={"a": 1},
                )

        class StepB(PipelineStep):
            name = "step_b"
            version = "1.0"

            def should_run(self, ctx):
                return True

            def execute(self, ctx):
                executed_steps.append("step_b")
                return StepResult(
                    success=True, artifact_kind="b",
                    artifact_payload={"b": 2},
                )

        run = _make_run(
            db, admin_setup["iteration"].id, "running",
            triggered_by=admin_setup["user"].id,
        )

        ctx = PipelineContext(
            db=db,
            ai_client=None,
            run=run,
            iteration_id=admin_setup["iteration"].id,
            config={},
        )

        runner = PipelineRunner("cancel_test", [StepA, StepB])

        with patch.object(pipeline_service, "update_run_status") as mock_update:
            mock_update.return_value = run

            original_execute = StepA.execute

            def _execute_and_cancel(self_step, ctx_inner):
                result = original_execute(self_step, ctx_inner)
                # 模拟 API 端点写入 cancelled 状态
                fresh_run = (
                    ctx_inner.db.query(PipelineRun)
                    .filter(PipelineRun.id == ctx_inner.run.id)
                    .first()
                )
                if fresh_run:
                    fresh_run.status = "cancelled"
                    ctx_inner.db.flush()
                return result

            with patch.object(StepA, "execute", _execute_and_cancel):
                runner.run(ctx)

        # StepA 应执行，StepB 不应执行（Runner 检测到 cancelled 后停止）
        assert "step_a" in executed_steps
        assert "step_b" not in executed_steps


# ── 响应格式测试 ──────────────────────────────────────────────────────


class TestCancelResponseFormat:
    """取消接口响应格式验证。"""

    def test_cancel_response_contains_required_fields(self, client, db, admin_setup):
        """取消成功后响应应包含 run_id、status、finished_at。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "running",
            triggered_by=admin_setup["user"].id,
        )
        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 200
        assert body["msg"] == "Pipeline 运行已取消"

        data = body["data"]
        assert data["run_id"] == run.id
        assert data["status"] == "cancelled"
        assert data["finished_at"] is not None

    def test_cancel_sets_finished_at(self, client, db, admin_setup):
        """取消后 finished_at 应被设置。"""
        run = _make_run(
            db, admin_setup["iteration"].id, "running",
            triggered_by=admin_setup["user"].id,
        )
        assert run.finished_at is None

        resp = client.post(
            f"/api/v1/pipeline/{run.id}/cancel",
            headers=admin_setup["headers"],
        )
        assert resp.status_code == 200

        db.refresh(run)
        assert run.finished_at is not None


# ── 权限服务单元测试 ──────────────────────────────────────────────────


class TestCheckPipelinePermissionForCancel:
    """pipeline_permission_service 中 cancel 权限的单元验证。"""

    def test_admin_has_cancel_all(self, db, admin_setup):
        """admin 角色应拥有 pipeline:cancel:all 权限。"""
        assert check_pipeline_permission(
            db, admin_setup["user"].id, "pipeline", "cancel", "all",
            project_id=admin_setup["project"].id,
        ) is True

    def test_qa_lead_has_cancel_own(self, db, qa_lead_setup):
        """qa_lead 角色应拥有 pipeline:cancel:own 权限。"""
        assert check_pipeline_permission(
            db, qa_lead_setup["user"].id, "pipeline", "cancel", "own",
            project_id=qa_lead_setup["project"].id,
        ) is True

    def test_qa_lead_no_cancel_all(self, db, qa_lead_setup):
        """qa_lead 角色不应拥有 pipeline:cancel:all 权限。"""
        assert check_pipeline_permission(
            db, qa_lead_setup["user"].id, "pipeline", "cancel", "all",
            project_id=qa_lead_setup["project"].id,
        ) is False

    def test_qa_engineer_no_cancel(self, db, qa_engineer_setup):
        """qa_engineer 角色不应拥有任何 cancel 权限。"""
        assert check_pipeline_permission(
            db, qa_engineer_setup["user"].id, "pipeline", "cancel", "own",
            project_id=qa_engineer_setup["project"].id,
        ) is False


# ── 状态转换测试 ──────────────────────────────────────────────────────


class TestCancelTransitionValidation:
    """取消状态转换合法性验证（_errors.py PIPELINE_RUN_TRANSITIONS）。"""

    def test_running_to_cancelled_is_valid(self):
        """running -> cancelled 应为合法状态转换。"""
        from app.services.pipeline_service._errors import PIPELINE_RUN_TRANSITIONS
        assert ("running", "cancelled") in PIPELINE_RUN_TRANSITIONS

    def test_waiting_for_user_to_cancelled_is_valid(self):
        """waiting_for_user -> cancelled 应为合法状态转换。"""
        from app.services.pipeline_service._errors import PIPELINE_RUN_TRANSITIONS
        assert ("waiting_for_user", "cancelled") in PIPELINE_RUN_TRANSITIONS

    def test_pending_to_cancelled_is_valid(self):
        """pending -> cancelled 应为合法状态转换。"""
        from app.services.pipeline_service._errors import PIPELINE_RUN_TRANSITIONS
        assert ("pending", "cancelled") in PIPELINE_RUN_TRANSITIONS

    def test_completed_to_cancelled_is_invalid(self):
        """completed -> cancelled 应为非法状态转换。"""
        from app.services.pipeline_service._errors import PIPELINE_RUN_TRANSITIONS
        assert ("completed", "cancelled") not in PIPELINE_RUN_TRANSITIONS

    def test_failed_to_cancelled_is_invalid(self):
        """failed -> cancelled 应为非法状态转换。"""
        from app.services.pipeline_service._errors import PIPELINE_RUN_TRANSITIONS
        assert ("failed", "cancelled") not in PIPELINE_RUN_TRANSITIONS
