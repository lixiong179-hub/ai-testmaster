"""
Pipeline 暂停超时自动取消服务测试模块

覆盖：
    - 正常超时取消
    - 未超时不触发
    - 边界值（恰好 7 天）
    - 超时天数从 config_service 动态读取
    - 审计日志写入
    - paused_at 为 None 时跳过
    - 配置值异常时使用默认值
    - 单条取消失败不影响其他记录
"""
from datetime import timedelta
import hashlib

import pytest
from sqlalchemy.orm import Session

from app.models.pipeline import PipelineRun
from app.models.enums import PipelineRunStatus
from app.models.iteration import Iteration
from app.services.pipeline_timeout_service import cancel_timed_out_pipelines
from app.services.config_service import set_config, clear_cache
from app.services.audit_service import query_logs
from app.utils.db_time import utcnow


@pytest.fixture(autouse=True)
def _reset_config_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def testIteration(db, testProject):
    """创建测试用迭代（依赖 conftest 的 testProject）。"""
    iteration = Iteration(
        name="timeout_test_iteration",
        project_id=testProject.id,
        version="v1.0",
    )
    db.add(iteration)
    db.flush()
    yield iteration


def _create_pipeline_run(
    db: Session, iteration_id: int, status: str,
    paused_at=None, input_hash: str = "test_hash_timeout",
) -> PipelineRun:
    """辅助函数：创建 PipelineRun 记录。"""
    uniqueHash = hashlib.sha256(
        f"{input_hash}{id(paused_at)}".encode()
    ).hexdigest()[:16]
    run = PipelineRun(
        iteration_id=iteration_id,
        input_hash=uniqueHash,
        pipeline_version="1.0",
        status=status,
        paused_at=paused_at,
    )
    db.add(run)
    db.flush()
    return run


class TestCancelTimedOutPipelines:
    """cancel_timed_out_pipelines 核心逻辑测试。"""

    def test_cancel_timed_out_run(self, db, testIteration):
        """暂停超过 7 天的运行应被自动取消。"""
        eightDaysAgo = utcnow() - timedelta(days=8)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_8days",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 1
        db.refresh(run)
        assert run.status == PipelineRunStatus.CANCELLED.value
        assert run.finished_at is not None

    def test_not_cancel_recently_paused(self, db, testIteration):
        """暂停不足 7 天的运行不应被取消。"""
        oneDayAgo = utcnow() - timedelta(days=1)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=oneDayAgo,
            input_hash="timeout_1day",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 0
        db.refresh(run)
        assert run.status == PipelineRunStatus.WAITING_FOR_USER.value

    def test_boundary_exactly_seven_days(self, db, testIteration):
        """恰好 7 天减 1 秒的暂停不应被取消（严格小于才触发）。"""
        almostSevenDays = utcnow() - timedelta(days=7, seconds=-1)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=almostSevenDays,
            input_hash="timeout_7days_exact",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 0
        db.refresh(run)
        assert run.status == PipelineRunStatus.WAITING_FOR_USER.value

    def test_boundary_just_over_seven_days(self, db, testIteration):
        """超过 7 天 1 秒的暂停应被取消。"""
        justOver = utcnow() - timedelta(days=7, seconds=1)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=justOver,
            input_hash="timeout_7days_plus1s",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 1
        db.refresh(run)
        assert run.status == PipelineRunStatus.CANCELLED.value

    def test_dynamic_timeout_from_config(self, db, testIteration):
        """超时天数从 config_service 动态读取。"""
        set_config(db, "PIPELINE_PAUSE_TIMEOUT_DAYS", 3)
        fourDaysAgo = utcnow() - timedelta(days=4)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=fourDaysAgo,
            input_hash="timeout_config_3days",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 1
        db.refresh(run)
        assert run.status == PipelineRunStatus.CANCELLED.value

    def test_audit_log_written(self, db, testIteration):
        """取消超时运行时应写入审计日志。"""
        eightDaysAgo = utcnow() - timedelta(days=8)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_audit",
        )

        cancel_timed_out_pipelines(db)

        logs = query_logs(db, action="pipeline_cancel_timeout")
        assert len(logs) >= 1
        log = logs[0]
        assert log.target_id == run.id
        assert log.target_kind == "pipeline_run"
        assert log.detail is not None
        assert log.detail["reason"] == "pause_timeout"
        assert log.detail["timeout_days"] == 7

    def test_skip_paused_at_none(self, db, testIteration):
        """paused_at 为 None 的 waiting_for_user 记录应被跳过。"""
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=None,
            input_hash="timeout_no_paused_at",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 0
        db.refresh(run)
        assert run.status == PipelineRunStatus.WAITING_FOR_USER.value

    def test_skip_non_waiting_status(self, db, testIteration):
        """非 waiting_for_user 状态的记录不应被取消。"""
        eightDaysAgo = utcnow() - timedelta(days=8)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.RUNNING.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_running_status",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 0
        db.refresh(run)
        assert run.status == PipelineRunStatus.RUNNING.value

    def test_config_invalid_value_uses_default(self, db, testIteration):
        """配置值异常时应使用默认值 7。"""
        from app.models.pipeline_config import PipelineConfig
        row = PipelineConfig(
            key="PIPELINE_PAUSE_TIMEOUT_DAYS",
            value="-1",
            value_type="int",
        )
        db.add(row)
        db.flush()
        clear_cache()

        eightDaysAgo = utcnow() - timedelta(days=8)
        run = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_invalid_config",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 1
        db.refresh(run)
        assert run.status == PipelineRunStatus.CANCELLED.value

    def test_multiple_timed_out_runs(self, db, testIteration):
        """多条超时记录应全部被取消。"""
        eightDaysAgo = utcnow() - timedelta(days=8)
        tenDaysAgo = utcnow() - timedelta(days=10)
        run1 = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_multi_1",
        )
        run2 = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=tenDaysAgo,
            input_hash="timeout_multi_2",
        )

        count = cancel_timed_out_pipelines(db)

        assert count == 2
        db.refresh(run1)
        db.refresh(run2)
        assert run1.status == PipelineRunStatus.CANCELLED.value
        assert run2.status == PipelineRunStatus.CANCELLED.value

    def test_no_timed_out_runs_returns_zero(self, db, testIteration):
        """无超时记录时返回 0。"""
        count = cancel_timed_out_pipelines(db)
        assert count == 0

    def test_single_cancel_failure_continues(self, db, testIteration):
        """单条取消失败时不应影响其他记录的取消。"""
        from unittest.mock import patch
        eightDaysAgo = utcnow() - timedelta(days=8)
        run1 = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_fail_1",
        )
        run2 = _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_fail_2",
        )

        callCount = {"n": 0}
        from app.services.pipeline_service._run import update_run_status as originalUpdate

        def _flaky_update(db, run_id, status, **kwargs):
            callCount["n"] += 1
            if callCount["n"] == 1:
                raise RuntimeError("模拟取消失败")
            return originalUpdate(db, run_id, status, **kwargs)

        with patch(
            "app.services.pipeline_service._run.update_run_status",
            side_effect=_flaky_update,
        ):
            count = cancel_timed_out_pipelines(db)

        assert count == 1
        db.refresh(run2)
        assert run2.status == PipelineRunStatus.CANCELLED.value

    def test_cancel_failure_returns_zero(self, db, testIteration):
        """取消过程中 flush/commit 失败时，异常被捕获，返回 0。"""
        from unittest.mock import patch
        eightDaysAgo = utcnow() - timedelta(days=8)
        _create_pipeline_run(
            db, testIteration.id,
            PipelineRunStatus.WAITING_FOR_USER.value,
            paused_at=eightDaysAgo,
            input_hash="timeout_flush_fail",
        )

        with patch.object(db, "commit", side_effect=RuntimeError("commit error")):
            count = cancel_timed_out_pipelines(db)

        assert count == 0
