"""Celery 应用工厂（Phase 1 Task 3：分布式测试执行引擎）

业务用途：测试任务经 Celery + Redis 分布式调度，Worker 水平扩展，支持 ≥50 并发。
设计原则：
1. 应用工厂模式，便于测试与多环境部署；
2. 复用 Redis broker（DB 0）与 backend（DB 2）；
3. task_acks_late=True + task_reject_on_worker_lost=True 保证任务不丢；
4. 单 Worker 内 asyncio.run 串行，避免嵌套事件循环。

依赖：celery[redis]==5.4.0、app.core.config
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_celery_app = None


def _resolve_broker_url() -> str:
    """解析 Celery broker URL，默认复用 Redis DB 0。"""
    if settings.CELERY_BROKER_URL:
        return settings.CELERY_BROKER_URL
    # 从 REDIS_URL 派生 broker URL（默认 DB 0）
    base = settings.REDIS_URL.rstrip("/")
    if "?" in base:
        base = base.split("?", 1)[0]
    # 移除 /N 后缀
    if "/" in base and base.rsplit("/", 1)[-1].isdigit():
        base = base.rsplit("/", 1)[0]
    return f"{base}/0"


def _resolve_backend_url() -> str:
    """解析 Celery result backend URL，默认复用 Redis DB 2。"""
    if settings.CELERY_RESULT_BACKEND:
        return settings.CELERY_RESULT_BACKEND
    base = settings.REDIS_URL.rstrip("/")
    if "?" in base:
        base = base.split("?", 1)[0]
    if "/" in base and base.rsplit("/", 1)[-1].isdigit():
        base = base.rsplit("/", 1)[0]
    return f"{base}/2"


def create_celery_app():
    """创建 Celery 应用实例。

    边界场景：
    1. settings.CELERY_ENABLED=False 时仍创建实例（便于测试），但端点不会调用 task.delay()
    2. Redis 不可用时 Celery 应用可创建，但任务投递会失败（端点降级走同步路径）
    """
    from celery import Celery

    app = Celery(
        "ai_testmaster",
        broker=_resolve_broker_url(),
        backend=_resolve_backend_url(),
        include=[
            "app.tasks.test_execution",
            "app.tasks.scheduler",
        ],
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_acks_late=settings.CELERY_TASK_ACKS_LATE,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
        task_track_started=True,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_default_max_retries=settings.CELERY_TASK_MAX_RETRIES,
        # 失败任务转入 DLQ（dead letter queue）
        task_routes={
            "app.tasks.test_execution.*": {"queue": "test_execution"},
            "app.tasks.scheduler.*": {"queue": "scheduler"},
        },
    )

    logger.info(
        f"Celery 应用已创建: broker={_resolve_broker_url()}, "
        f"backend={_resolve_backend_url()}, enabled={settings.CELERY_ENABLED}"
    )
    return app


def get_celery_app():
    """获取 Celery 应用单例（懒加载）。"""
    global _celery_app
    if _celery_app is None:
        _celery_app = create_celery_app()
    return _celery_app
