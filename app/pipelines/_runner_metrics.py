"""Pipeline FMEA 监控指标记录辅助模块。

从 runner.py 拆分而来，负责在 Pipeline 运行过程中记录 FMEA 监控指标。
指标记录失败不阻塞业务流程。
"""
import logging
from typing import Optional

from app.models.iteration import Iteration
from app.pipelines.context import PipelineContext

logger = logging.getLogger(__name__)


def _record_fmea_metric(
    ctx: PipelineContext,
    metric_name: str,
    *,
    step_name: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    """在 Pipeline 运行中记录 FMEA 监控指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        project_id = ctx._cached_project_id
        if project_id is None and ctx.iteration_id:
            iteration = ctx.db.query(Iteration).filter(
                Iteration.id == ctx.iteration_id,
            ).first()
            if iteration:
                project_id = iteration.project_id
            ctx._cached_project_id = project_id
        record_metric(
            metric_name,
            project_id=project_id,
            iteration_id=ctx.iteration_id,
            run_id=ctx.run.id,
            step_name=step_name,
            detail=detail,
        )
    except Exception as e:
        logger.warning("FMEA metric recording failed: %s", e)
