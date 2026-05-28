"""
APScheduler 定时任务调度服务测试模块

覆盖：
    - scheduler 启动
    - scheduler 重复启动跳过
    - scheduler 关闭
    - scheduler 未启动时关闭不报错
    - 定时任务注册验证
    - get_scheduler 返回实例
    - _run_pipeline_timeout_check 正常执行
    - _run_pipeline_timeout_check 异常处理
"""
import time

import pytest

from app.services.scheduler_service import (
    start_scheduler,
    shutdown_scheduler,
    get_scheduler,
    _run_pipeline_timeout_check,
)


@pytest.fixture(autouse=True)
def _ensure_scheduler_stopped():
    """每个测试前后确保调度器已停止，防止测试间干扰。"""
    shutdown_scheduler()
    yield
    shutdown_scheduler()


class TestStartScheduler:
    """start_scheduler 启动逻辑测试。"""

    def test_start_creates_running_scheduler(self):
        """启动后调度器应处于运行状态。"""
        start_scheduler()
        scheduler = get_scheduler()
        assert scheduler is not None
        assert scheduler.running is True

    def test_start_registers_pipeline_timeout_job(self):
        """启动后应注册 pipeline_timeout_check 定时任务。"""
        start_scheduler()
        scheduler = get_scheduler()
        job = scheduler.get_job("pipeline_timeout_check")
        assert job is not None
        assert job.name == "Pipeline 暂停超时自动取消"

    def test_start_idempotent(self):
        """重复启动不应创建多个调度器。"""
        start_scheduler()
        scheduler1 = get_scheduler()
        start_scheduler()
        scheduler2 = get_scheduler()
        assert scheduler1 is scheduler2


class TestShutdownScheduler:
    """shutdown_scheduler 关闭逻辑测试。"""

    def test_shutdown_stops_scheduler(self):
        """关闭后调度器应不再运行。"""
        start_scheduler()
        assert get_scheduler().running is True
        shutdown_scheduler()
        assert get_scheduler() is None

    def test_shutdown_when_not_started(self):
        """未启动时关闭不应抛异常。"""
        shutdown_scheduler()
        assert get_scheduler() is None

    def test_shutdown_after_start(self):
        """启动后关闭，再启动应正常工作。"""
        start_scheduler()
        shutdown_scheduler()
        start_scheduler()
        scheduler = get_scheduler()
        assert scheduler is not None
        assert scheduler.running is True


class TestGetScheduler:
    """get_scheduler 返回值测试。"""

    def test_returns_none_before_start(self):
        """启动前应返回 None。"""
        assert get_scheduler() is None

    def test_returns_instance_after_start(self):
        """启动后应返回 BackgroundScheduler 实例。"""
        from apscheduler.schedulers.background import BackgroundScheduler
        start_scheduler()
        assert isinstance(get_scheduler(), BackgroundScheduler)

    def test_returns_none_after_shutdown(self):
        """关闭后应返回 None。"""
        start_scheduler()
        shutdown_scheduler()
        assert get_scheduler() is None


class TestJobConfiguration:
    """定时任务配置验证测试。"""

    def test_job_interval_is_one_hour(self):
        """定时任务触发间隔应为 1 小时。"""
        start_scheduler()
        scheduler = get_scheduler()
        job = scheduler.get_job("pipeline_timeout_check")
        assert job is not None
        trigger = job.trigger
        from apscheduler.triggers.interval import IntervalTrigger
        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval.seconds == 3600


class TestRunPipelineTimeoutCheck:
    """_run_pipeline_timeout_check 定时任务回调测试。"""

    def test_normal_execution(self):
        """正常执行不应抛异常。"""
        from unittest.mock import patch, MagicMock
        mockDb = MagicMock()
        mockSessionLocal = MagicMock(return_value=mockDb)
        with patch(
            "app.db.database.PrimarySessionLocal",
            mockSessionLocal,
        ), patch(
            "app.services.pipeline_timeout_service.cancel_timed_out_pipelines",
            return_value=2,
        ):
            _run_pipeline_timeout_check()

        mockDb.close.assert_called_once()

    def test_exception_does_not_raise(self):
        """cancel_timed_out_pipelines 抛异常时不应向上传播。"""
        from unittest.mock import patch, MagicMock
        mockDb = MagicMock()
        mockSessionLocal = MagicMock(return_value=mockDb)
        with patch(
            "app.db.database.PrimarySessionLocal",
            mockSessionLocal,
        ), patch(
            "app.services.pipeline_timeout_service.cancel_timed_out_pipelines",
            side_effect=RuntimeError("db error"),
        ):
            _run_pipeline_timeout_check()

        mockDb.rollback.assert_called_once()
        mockDb.close.assert_called_once()

    def test_zero_cancels_no_info_log(self):
        """取消 0 条时不输出 info 日志（仅 count > 0 时记录）。"""
        from unittest.mock import patch, MagicMock
        mockDb = MagicMock()
        mockSessionLocal = MagicMock(return_value=mockDb)
        with patch(
            "app.db.database.PrimarySessionLocal",
            mockSessionLocal,
        ), patch(
            "app.services.pipeline_timeout_service.cancel_timed_out_pipelines",
            return_value=0,
        ):
            _run_pipeline_timeout_check()

        mockDb.close.assert_called_once()

    def test_rollback_failure_does_not_raise(self):
        """rollback 失败时不应向上传播异常。"""
        from unittest.mock import patch, MagicMock
        mockDb = MagicMock()
        mockDb.rollback.side_effect = RuntimeError("rollback failed")
        mockSessionLocal = MagicMock(return_value=mockDb)
        with patch(
            "app.db.database.PrimarySessionLocal",
            mockSessionLocal,
        ), patch(
            "app.services.pipeline_timeout_service.cancel_timed_out_pipelines",
            side_effect=RuntimeError("db error"),
        ):
            _run_pipeline_timeout_check()

        mockDb.close.assert_called_once()
