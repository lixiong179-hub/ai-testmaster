"""Celery Beat 调度任务（Phase 1 Task 3：APScheduler 迁移）

业务用途：将 APScheduler 的 pipeline_timeout_check 迁移至 Celery Beat，
实现调度器无状态化，支持多实例部署避免重复执行。

设计原则：
1. Beat 仅在主节点运行（单实例），Worker 多实例水平扩展；
2. 任务复用现有 pipeline_timeout_service 逻辑，零业务行为变更；
3. 灰度策略：CELERY_ENABLED=False 时仍由 APScheduler 执行，避免回退风险。

依赖：app.tasks.celery_app、app.services.pipeline_timeout_service
"""
import logging

from app.tasks._async_bridge import async_task
from app.tasks.base import BaseTask
from app.tasks.celery_app import get_celery_app

logger = logging.getLogger(__name__)

celery_app = get_celery_app()


@celery_app.task(
    bind=True,
    base=BaseTask,
    name="app.tasks.scheduler.pipeline_timeout_check",
    queue="scheduler",
)
def pipeline_timeout_check_task(self) -> dict:
    """扫描并取消暂停超时的 Pipeline 运行。

    业务用途：每小时扫描 status=pause 且 pause_time 超过 PIPELINE_PAUSE_TIMEOUT_DAYS
    的 Pipeline 运行，自动取消避免资源占用。

    迁移说明：原 APScheduler _run_pipeline_timeout_check 逻辑迁入此处，
    APScheduler 保留作为单机兜底（CELERY_ENABLED=False 时启用）。
    """
    self.on_start(self.request.id, args=(), kwargs={})
    logger.info(f"执行 Pipeline 超时检查: task_id={self.request.id}")

    from app.db.database import PrimarySessionLocal
    from app.services.pipeline_timeout_service import cancel_timed_out_pipelines

    db = PrimarySessionLocal()
    try:
        cancelled_count = cancel_timed_out_pipelines(db)
        logger.info(f"Pipeline 超时检查完成: task_id={self.request.id}, 取消 {cancelled_count} 个")
        return {"cancelled_count": cancelled_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Pipeline 超时检查失败: task_id={self.request.id}, error={e}")
        raise
    finally:
        db.close()


def get_beat_schedule() -> dict:
    """生成 Celery Beat 调度配置。

    业务用途：替代 celery beat-schedule 文件，集中管理周期任务。
    边界场景：CELERY_ENABLED=False 时不启用 Beat（APScheduler 兜底）。
    """
    from app.core.config import settings

    return {
        "pipeline-timeout-check": {
            "task": "app.tasks.scheduler.pipeline_timeout_check",
            "schedule": settings.CELERY_BEAT_PIPELINE_TIMEOUT_INTERVAL,
            "options": {"queue": "scheduler"},
        },
    }
