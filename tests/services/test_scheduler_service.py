"""
APScheduler 定时任务调度服务测试模块

覆盖：
    - start_scheduler 首次启动与重复启动防护
    - shutdown_scheduler 已停止/正常运行后关闭
    - get_scheduler 返回实例与关闭后置 None
    - _run_pipeline_timeout_check 正常执行与异常捕获

测试约定：
    - 使用真实测试库 SessionLocal 替换 PrimarySessionLocal，避免触碰生产库
    - cancel_timed_out_pipelines 异常场景使用 monkeypatch 注入（边界测试）
    - 每个测试前后调用 shutdown_scheduler() 确保无残留调度器
"""
from typing import Any, Iterator

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session, sessionmaker

from app.db import database as dbModule
from app.services import pipeline_timeout_service
from app.services.scheduler_service import (
    _run_pipeline_timeout_check,
    get_scheduler,
    shutdown_scheduler,
    start_scheduler,
)


@pytest.fixture(autouse=True)
def ensureSchedulerStopped() -> Iterator[None]:
    """每个测试前后确保调度器已停止并清理全局引用，防止测试间干扰。

    shutdown_scheduler 在 _scheduler 未运行时直接返回不置 None，
    需手动重置避免残留调度器引用泄漏到后续测试。
    """
    import app.services.scheduler_service as svc
    shutdown_scheduler()
    if svc._scheduler is not None and not svc._scheduler.running:
        svc._scheduler = None
    yield
    shutdown_scheduler()
    if svc._scheduler is not None and not svc._scheduler.running:
        svc._scheduler = None


class _TrackingSession:
    """包装真实 Session，跟踪 rollback/close 调用次数。

    用于 _run_pipeline_timeout_check 异常路径验证：确认 rollback 与
    close 被调用。这不是 Mock，仅是行为记录包装器，内部委托真实
    Session 保证事务语义。
    """

    def __init__(self, realSession: Session) -> None:
        self._real = realSession
        self.rollbackCalls: int = 0
        self.closeCalls: int = 0

    def rollback(self) -> None:
        self.rollbackCalls += 1
        self._real.rollback()

    def close(self) -> None:
        self.closeCalls += 1
        self._real.close()

    def __getattr__(self, name: str) -> Any:
        # 透传未显式覆盖的属性到真实 Session（如 query、commit、execute）
        return getattr(self._real, name)


class TestStartScheduler:
    """start_scheduler 启动逻辑测试。"""

    def test_start_creates_running_scheduler(self) -> None:
        """首次启动应创建 BackgroundScheduler 并处于运行状态。"""
        start_scheduler()
        scheduler = get_scheduler()
        assert scheduler is not None
        assert isinstance(scheduler, BackgroundScheduler)
        assert scheduler.running is True

    def test_start_registers_pipeline_timeout_job(self) -> None:
        """启动后应注册 pipeline_timeout_check 定时任务。"""
        start_scheduler()
        scheduler = get_scheduler()
        job = scheduler.get_job("pipeline_timeout_check")
        assert job is not None
        assert job.name == "Pipeline 暂停超时自动取消"

    def test_start_job_uses_one_hour_interval(self) -> None:
        """注册的定时任务触发间隔应为 1 小时。"""
        start_scheduler()
        scheduler = get_scheduler()
        job = scheduler.get_job("pipeline_timeout_check")
        assert job is not None
        assert isinstance(job.trigger, IntervalTrigger)
        assert job.trigger.interval.total_seconds() == 3600

    def test_start_idempotent_skips_duplicate(self) -> None:
        """重复启动应跳过，不创建重复调度器，不抛异常。"""
        start_scheduler()
        scheduler1 = get_scheduler()
        start_scheduler()
        scheduler2 = get_scheduler()
        assert scheduler1 is scheduler2


class TestShutdownScheduler:
    """shutdown_scheduler 关闭逻辑测试。"""

    def test_shutdown_when_not_started(self) -> None:
        """_scheduler 为 None 时关闭不应抛异常。"""
        shutdown_scheduler()
        assert get_scheduler() is None

    def test_shutdown_after_start(self) -> None:
        """正常运行后关闭，调度器应停止且 _scheduler 置 None。"""
        start_scheduler()
        assert get_scheduler().running is True
        shutdown_scheduler()
        assert get_scheduler() is None

    def test_shutdown_when_stopped_but_not_none(self) -> None:
        """_scheduler 存在但未运行时关闭应安全返回（边界场景）。

        构造未启动的调度器模拟 _scheduler 存在但 not running 状态，
        shutdown_scheduler 应识别 not running 并直接返回，不抛异常、
        不调用 shutdown、不置 None（实现语义：仅运行中才关闭）。
        """
        import app.services.scheduler_service as svc
        stoppedScheduler = BackgroundScheduler()
        assert stoppedScheduler.running is False
        svc._scheduler = stoppedScheduler
        shutdown_scheduler()
        # not running 分支直接 return，_scheduler 引用不变
        assert get_scheduler() is stoppedScheduler


class TestGetScheduler:
    """get_scheduler 返回值测试。"""

    def test_returns_none_before_start(self) -> None:
        """启动前应返回 None。"""
        assert get_scheduler() is None

    def test_returns_instance_after_start(self) -> None:
        """启动后应返回 BackgroundScheduler 实例。"""
        start_scheduler()
        scheduler = get_scheduler()
        assert isinstance(scheduler, BackgroundScheduler)

    def test_returns_none_after_shutdown(self) -> None:
        """关闭后应返回 None。"""
        start_scheduler()
        shutdown_scheduler()
        assert get_scheduler() is None


class TestRunPipelineTimeoutCheck:
    """_run_pipeline_timeout_check 定时任务回调测试。

    使用真实测试库 SessionLocal 替换 PrimarySessionLocal，
    避免触碰生产库；cancel_timed_out_pipelines 异常场景用
    monkeypatch 注入（边界测试，符合规范）。
    """

    def test_normal_execution_no_exception(
        self, monkeypatch, testEngine
    ) -> None:
        """正常执行不应抛异常，使用真实测试库 session。

        空库下 cancel_timed_out_pipelines 查询返回空，直接 return 0，
        不触发 rollback，finally 关闭 session。
        """
        realLocal = sessionmaker(bind=testEngine)
        sessions: list[_TrackingSession] = []

        def trackingFactory() -> _TrackingSession:
            session = _TrackingSession(realLocal())
            sessions.append(session)
            return session

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", trackingFactory)
        _run_pipeline_timeout_check()

        assert len(sessions) == 1
        assert sessions[0].rollbackCalls == 0
        assert sessions[0].closeCalls == 1

    def test_exception_does_not_raise_and_calls_rollback_close(
        self, monkeypatch, testEngine
    ) -> None:
        """cancel_timed_out_pipelines 抛异常时不向上传播，rollback 与 close 被调用。"""
        realLocal = sessionmaker(bind=testEngine)
        sessions: list[_TrackingSession] = []

        def trackingFactory() -> _TrackingSession:
            session = _TrackingSession(realLocal())
            sessions.append(session)
            return session

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", trackingFactory)

        def raiseException(db: Session) -> None:
            raise RuntimeError("db error")

        monkeypatch.setattr(
            pipeline_timeout_service,
            "cancel_timed_out_pipelines",
            raiseException,
        )

        _run_pipeline_timeout_check()

        assert len(sessions) == 1
        assert sessions[0].rollbackCalls == 1
        assert sessions[0].closeCalls == 1

    def test_rollback_failure_does_not_raise(
        self, monkeypatch, testEngine
    ) -> None:
        """rollback 自身抛异常时不应向上传播（内层 except pass 兜底），close 仍被调用。"""
        realLocal = sessionmaker(bind=testEngine)
        sessions: list[_TrackingSession] = []

        class _RollbackFailureSession(_TrackingSession):
            def rollback(self) -> None:
                self.rollbackCalls += 1
                raise RuntimeError("rollback failed")

        def trackingFactory() -> _TrackingSession:
            session = _RollbackFailureSession(realLocal())
            sessions.append(session)
            return session

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", trackingFactory)

        def raiseException(db: Session) -> None:
            raise RuntimeError("db error")

        monkeypatch.setattr(
            pipeline_timeout_service,
            "cancel_timed_out_pipelines",
            raiseException,
        )

        _run_pipeline_timeout_check()

        assert len(sessions) == 1
        assert sessions[0].rollbackCalls == 1
        assert sessions[0].closeCalls == 1
