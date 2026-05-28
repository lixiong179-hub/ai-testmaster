"""
APScheduler 定时任务调度服务模块

本模块使用 APScheduler 的 BackgroundScheduler 注册定时任务，
通过 FastAPI 的 lifespan 事件管理调度器生命周期。

核心函数概览：
    - start_scheduler : 启动调度器并注册定时任务
    - shutdown_scheduler : 优雅关闭调度器

定时任务：
    - pipeline_timeout_check : 每小时扫描暂停超时的 Pipeline 运行

依赖关系：
    - apscheduler.schedulers.background : BackgroundScheduler
    - app.services.pipeline_timeout_service : cancel_timed_out_pipelines
    - app.db.database : PrimarySessionLocal
"""
from loguru import logger
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler: BackgroundScheduler | None = None


def _run_pipeline_timeout_check() -> None:
    """定时任务：扫描并取消暂停超时的 Pipeline 运行。

    每次执行时创建独立的数据库会话，确保事务隔离。
    异常不会中断调度器，仅记录日志。
    """
    from app.db.database import PrimarySessionLocal
    from app.services.pipeline_timeout_service import cancel_timed_out_pipelines

    db = PrimarySessionLocal()
    try:
        cancel_timed_out_pipelines(db)
    except Exception as e:
        logger.error("Pipeline 超时检查定时任务执行失败: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


def start_scheduler() -> None:
    """启动 APScheduler 调度器并注册定时任务。

    若调度器已启动则跳过，防止重复初始化。
    注册 pipeline_timeout_check 任务，每小时执行一次。
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("APScheduler 已在运行，跳过重复启动")
        return

    _scheduler = BackgroundScheduler()

    _scheduler.add_job(
        func=_run_pipeline_timeout_check,
        trigger="interval",
        hours=1,
        id="pipeline_timeout_check",
        name="Pipeline 暂停超时自动取消",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("APScheduler 调度器已启动，注册任务: pipeline_timeout_check (每小时)")


def shutdown_scheduler() -> None:
    """优雅关闭 APScheduler 调度器。

    等待正在执行的任务完成后关闭。
    注意：APScheduler 3.x 的 shutdown(wait=True) 不支持超时参数，
    若任务长时间阻塞可能导致关闭过程无法结束。
    """
    global _scheduler

    if _scheduler is None or not _scheduler.running:
        return

    _scheduler.shutdown(wait=True)
    logger.info("APScheduler 调度器已关闭")
    _scheduler = None


def get_scheduler() -> BackgroundScheduler | None:
    """获取当前调度器实例（用于测试和外部检查）。"""
    return _scheduler
