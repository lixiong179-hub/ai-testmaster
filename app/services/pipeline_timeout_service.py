"""
Pipeline 暂停超时自动取消服务模块

本模块扫描 pipeline_run 表中 status='waiting_for_user' 且
paused_at 超过配置天数的记录，自动取消并记录审计日志。

核心函数概览：
    - cancel_timed_out_pipelines : 扫描并取消超时的 Pipeline 运行

依赖关系：
    - app.models.pipeline : PipelineRun
    - app.models.enums : PipelineRunStatus
    - app.services.config_service : 读取 PIPELINE_PAUSE_TIMEOUT_DAYS
    - app.services.audit_service : 写入审计日志
    - app.services.pipeline_service._run : update_run_status
"""
from datetime import timedelta

from loguru import logger
from sqlalchemy.orm import Session

from app.models.pipeline import PipelineRun
from app.models.enums import PipelineRunStatus
from app.services.config_service import get_config
from app.utils.db_time import utcnow


def cancel_timed_out_pipelines(db: Session) -> int:
    """扫描并取消暂停超时的 Pipeline 运行。

    查询 status='waiting_for_user' 且 paused_at < now() - timeout_days
    的记录，逐条取消并写入审计日志。超时天数从 config_service 动态读取。

    Args:
        db: 数据库会话。

    Returns:
        取消的记录数。
    """
    timeoutDays = get_config(
        db, "PIPELINE_PAUSE_TIMEOUT_DAYS", default=7,
    )
    if not isinstance(timeoutDays, (int, float)) or timeoutDays <= 0:
        logger.warning(
            "PIPELINE_PAUSE_TIMEOUT_DAYS 配置值异常: {}，使用默认值 7",
            timeoutDays,
        )
        timeoutDays = 7

    cutoffTime = utcnow() - timedelta(days=timeoutDays)

    timedOutRuns = (
        db.query(PipelineRun)
        .filter(
            PipelineRun.status == PipelineRunStatus.WAITING_FOR_USER.value,
            PipelineRun.paused_at.isnot(None),
            PipelineRun.paused_at < cutoffTime,
        )
        .all()
    )

    if not timedOutRuns:
        return 0

    cancelledCount = 0
    for run in timedOutRuns:
        nested = db.begin_nested()
        try:
            _cancel_single_run(db, run, timeoutDays)
            db.commit()
            cancelledCount += 1
        except Exception as e:
            logger.error(
                "取消超时 PipelineRun id={} 失败: {}",
                run.id, e,
            )
            try:
                if nested.is_active:
                    nested.rollback()
            except Exception:
                pass

    if cancelledCount > 0:
        logger.info(
            "Pipeline 暂停超时扫描完成: 共 {} 条超时，成功取消 {} 条",
            len(timedOutRuns), cancelledCount,
        )
    return cancelledCount


def _cancel_single_run(
    db: Session, run: PipelineRun, timeoutDays: int,
) -> None:
    """取消单条超时的 PipelineRun 并记录审计日志。

    Args:
        db: 数据库会话。
        run: 待取消的 PipelineRun 实例。
        timeoutDays: 超时天数。
    """
    from app.services.pipeline_service._run import update_run_status
    from app.services.audit_service import log_action

    update_run_status(
        db=db,
        run_id=run.id,
        status=PipelineRunStatus.CANCELLED.value,
        error=f"Pipeline 暂停超过 {timeoutDays} 天未确认，自动取消",
    )

    log_action(
        db=db,
        action="pipeline_cancel_timeout",
        actor_id=None,
        target_kind="pipeline_run",
        target_id=run.id,
        detail={
            "reason": "pause_timeout",
            "timeout_days": timeoutDays,
            "paused_at": run.paused_at.isoformat() if run.paused_at else None,
        },
        run_id=run.id,
        iteration_id=run.iteration_id,
    )
