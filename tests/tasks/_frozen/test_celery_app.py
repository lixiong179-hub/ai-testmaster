"""Celery 任务模块单元测试（Phase 1 Task 3）

测试对象：app/tasks/celery_app.py、app/tasks/base.py、app/tasks/_async_bridge.py、app/tasks/scheduler.py
依赖：mock Redis/Celery broker，禁止真实 Redis 调用
运行：python -m pytest tests/tasks/test_celery_app.py -v --tb=short
"""
import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

# 导入任务模块触发注册（include 仅在 Worker 启动时生效，测试需显式导入）
import app.tasks.test_execution  # noqa: F401
import app.tasks.scheduler  # noqa: F401


class TestCeleryAppFactory:
    """Celery 应用工厂测试。"""

    def test_create_celery_app_returns_app(self):
        """create_celery_app 返回 Celery 实例。"""
        from app.tasks.celery_app import create_celery_app
        app = create_celery_app()
        assert app.main == "ai_testmaster"
        assert "app.tasks.test_execution" in app.conf.include
        assert "app.tasks.scheduler" in app.conf.include

    def test_get_celery_app_singleton(self):
        """get_celery_app 单例缓存。"""
        from app.tasks.celery_app import get_celery_app
        app1 = get_celery_app()
        app2 = get_celery_app()
        assert app1 is app2

    def test_celery_app_config_acks_late(self):
        """task_acks_late 配置正确（崩溃任务重投）。"""
        from app.tasks.celery_app import get_celery_app
        from app.core.config import settings
        app = get_celery_app()
        assert app.conf.task_acks_late is settings.CELERY_TASK_ACKS_LATE

    def test_celery_app_config_reject_on_worker_lost(self):
        """task_reject_on_worker_lost 配置正确。"""
        from app.tasks.celery_app import get_celery_app
        app = get_celery_app()
        assert app.conf.task_reject_on_worker_lost is True

    def test_celery_app_task_routes(self):
        """任务路由配置正确（按队列分组）。"""
        from app.tasks.celery_app import get_celery_app
        app = get_celery_app()
        routes = app.conf.task_routes
        assert "app.tasks.test_execution.*" in routes
        assert routes["app.tasks.test_execution.*"]["queue"] == "test_execution"
        assert routes["app.tasks.scheduler.*"]["queue"] == "scheduler"


class TestBrokerUrlResolution:
    """Broker URL 解析逻辑测试。"""

    def test_resolve_broker_url_explicit(self):
        """显式配置 CELERY_BROKER_URL 时优先使用。"""
        from app.tasks.celery_app import _resolve_broker_url
        with patch("app.tasks.celery_app.settings.CELERY_BROKER_URL", "redis://broker:6379/0"):
            assert _resolve_broker_url() == "redis://broker:6379/0"

    def test_resolve_broker_url_from_redis_url(self):
        """从 REDIS_URL 派生 broker URL（默认 DB 0）。"""
        from app.tasks.celery_app import _resolve_broker_url
        with patch("app.tasks.celery_app.settings.CELERY_BROKER_URL", ""), \
                patch("app.tasks.celery_app.settings.REDIS_URL", "redis://localhost:6379/1"):
            assert _resolve_broker_url() == "redis://localhost:6379/0"

    def test_resolve_backend_url_explicit(self):
        """显式配置 CELERY_RESULT_BACKEND 时优先使用。"""
        from app.tasks.celery_app import _resolve_backend_url
        with patch("app.tasks.celery_app.settings.CELERY_RESULT_BACKEND", "redis://backend:6379/3"):
            assert _resolve_backend_url() == "redis://backend:6379/3"

    def test_resolve_backend_url_from_redis_url(self):
        """从 REDIS_URL 派生 backend URL（默认 DB 2）。"""
        from app.tasks.celery_app import _resolve_backend_url
        with patch("app.tasks.celery_app.settings.CELERY_RESULT_BACKEND", ""), \
                patch("app.tasks.celery_app.settings.REDIS_URL", "redis://localhost:6379/1"):
            assert _resolve_backend_url() == "redis://localhost:6379/2"


class TestAsyncBridge:
    """异步任务桥接器测试。"""

    def test_async_task_wraps_coroutine(self):
        """async_task 将 async def 包装为同步调用。"""
        from app.tasks._async_bridge import async_task

        @async_task
        async def add(a: int, b: int) -> int:
            await asyncio.sleep(0.01)
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_async_task_preserves_exception(self):
        """异步函数异常透传给调用方。"""
        from app.tasks._async_bridge import async_task

        @async_task
        async def fail():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            fail()

    def test_async_task_preserves_metadata(self):
        """functools.wraps 保留原函数元数据。"""
        from app.tasks._async_bridge import async_task

        @async_task
        async def my_func(x: int) -> int:
            """My docstring."""
            return x

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."


class TestBaseTask:
    """任务基类 BaseTask 测试。"""

    def test_calculate_retry_backoff(self):
        """指数退避计算正确。"""
        from app.tasks.base import calculate_retry_backoff
        assert calculate_retry_backoff(0) == 1
        assert calculate_retry_backoff(1) == 2
        assert calculate_retry_backoff(2) == 4
        assert calculate_retry_backoff(3) == 8
        assert calculate_retry_backoff(10) == 60  # 上限

    def test_task_state_constants(self):
        """任务状态常量定义正确。"""
        from app.tasks.base import (
            TASK_STATE_PENDING, TASK_STATE_STARTED,
            TASK_STATE_SUCCESS, TASK_STATE_FAILURE, TASK_STATE_RETRY,
        )
        assert TASK_STATE_PENDING == "pending"
        assert TASK_STATE_STARTED == "started"
        assert TASK_STATE_SUCCESS == "success"
        assert TASK_STATE_FAILURE == "failure"
        assert TASK_STATE_RETRY == "retry"

    def test_task_state_callback_redis_failure(self):
        """Redis 故障时 task_state_callback 不抛异常（仅告警）。"""
        from app.tasks.base import task_state_callback
        with patch("redis.from_url", side_effect=Exception("redis down")):
            # 不应抛异常
            task_state_callback("task-123", "started", None)

    def test_task_state_callback_writes_redis(self):
        """Redis 正常时 task_state_callback 写入状态。"""
        from app.tasks.base import task_state_callback
        mock_redis = MagicMock()
        with patch("redis.from_url", return_value=mock_redis):
            task_state_callback("task-456", "success", {"run_id": 1})
            mock_redis.hset.assert_called_once()
            mock_redis.expire.assert_called_once()
            mock_redis.close.assert_called_once()


class TestBaseTaskLifecycle:
    """BaseTask 生命周期回调测试。"""

    def test_on_success_callback(self):
        """on_success 回写 success 状态。"""
        from app.tasks.base import BaseTask, TASK_STATE_SUCCESS
        task = BaseTask()
        with patch("app.tasks.base.task_state_callback") as mock_cb:
            task.on_success({"run_id": 1}, "task-789", (), {})
            mock_cb.assert_called_once_with("task-789", TASK_STATE_SUCCESS, {"run_id": 1})

    def test_on_failure_callback(self):
        """on_failure 回写 failure 状态。"""
        from app.tasks.base import BaseTask, TASK_STATE_FAILURE
        task = BaseTask()
        with patch("app.tasks.base.task_state_callback") as mock_cb:
            task.on_failure(ValueError("test"), "task-fail", (), {}, MagicMock())
            mock_cb.assert_called_once_with("task-fail", TASK_STATE_FAILURE, "test")

    def test_on_retry_callback(self):
        """on_retry 回写 retry 状态。"""
        from app.tasks.base import BaseTask, TASK_STATE_RETRY
        from celery.app.task import Context
        task = BaseTask()
        # BaseTask 未绑定 app，request_stack 为 None，需手动初始化
        from celery import current_app
        task.bind(current_app)
        task.push_request(retries=1)
        try:
            with patch("app.tasks.base.task_state_callback") as mock_cb:
                task.on_retry(ConnectionError("redis down"), "task-retry", (), {}, MagicMock())
                mock_cb.assert_called_once_with("task-retry", TASK_STATE_RETRY, "redis down")
        finally:
            task.pop_request()


class TestSchedulerTask:
    """Celery Beat 调度任务测试。"""

    def test_pipeline_timeout_check_task_registered(self):
        """pipeline_timeout_check_task 已注册。"""
        from app.tasks.celery_app import get_celery_app
        app = get_celery_app()
        assert "app.tasks.scheduler.pipeline_timeout_check" in app.tasks

    def test_get_beat_schedule_returns_config(self):
        """get_beat_schedule 返回周期任务配置。"""
        from app.tasks.scheduler import get_beat_schedule
        schedule = get_beat_schedule()
        assert "pipeline-timeout-check" in schedule
        assert schedule["pipeline-timeout-check"]["task"] == "app.tasks.scheduler.pipeline_timeout_check"

    def test_get_beat_schedule_uses_config_interval(self):
        """get_beat_schedule 使用配置的间隔。"""
        from app.tasks.scheduler import get_beat_schedule
        from app.core.config import settings
        schedule = get_beat_schedule()
        assert schedule["pipeline-timeout-check"]["schedule"] == settings.CELERY_BEAT_PIPELINE_TIMEOUT_INTERVAL


class TestTestExecutionTask:
    """测试执行任务注册测试。"""

    def test_execute_pipeline_task_registered(self):
        """execute_pipeline_task 已注册。"""
        from app.tasks.celery_app import get_celery_app
        app = get_celery_app()
        assert "app.tasks.test_execution.execute_pipeline" in app.tasks

    def test_execute_pipeline_task_uses_base_task(self):
        """execute_pipeline_task 继承 BaseTask。"""
        from app.tasks.base import BaseTask
        from app.tasks.celery_app import get_celery_app
        app = get_celery_app()
        task = app.tasks["app.tasks.test_execution.execute_pipeline"]
        assert isinstance(task, BaseTask)

    def test_execute_pipeline_task_queue_routing(self):
        """execute_pipeline_task 路由至 test_execution 队列。"""
        from app.tasks.celery_app import get_celery_app
        app = get_celery_app()
        task = app.tasks["app.tasks.test_execution.execute_pipeline"]
        assert task.queue == "test_execution"


class TestWorkerEntry:
    """Worker 启动入口测试（仅验证函数存在，不实际启动）。"""

    def test_start_worker_function_exists(self):
        """start_worker 函数可导入。"""
        from app.tasks.worker import start_worker
        assert callable(start_worker)

    def test_start_beat_function_exists(self):
        """start_beat 函数可导入。"""
        from app.tasks.worker import start_beat
        assert callable(start_beat)

    def test_celery_app_in_worker_module(self):
        """worker 模块导出 celery_app 实例。"""
        from app.tasks.worker import celery_app
        assert celery_app.main == "ai_testmaster"
