import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.pipeline import PipelineRun, PipelineStep
from app.models.pipeline_metric import PipelineMetric
from app.ai.call_log import AICallLog
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_dashboard._utils import (
    duration_seconds,
    build_run_subquery,
)
from app.core.exception import create_response
from app.services.metrics_service import _date_trunc_day
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pipeline仪表盘"])


@router.get("/overview", response_model=dict)
def get_dashboard_overview(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        since = utcnow() - timedelta(days=days)

        total_runs = db.query(func.count(PipelineRun.id)).filter(PipelineRun.started_at >= since)
        completed_runs = db.query(func.count(PipelineRun.id)).filter(PipelineRun.started_at >= since, PipelineRun.status == "completed")
        total_tokens = db.query(
            func.coalesce(func.sum(AICallLog.prompt_tokens), 0)
            + func.coalesce(func.sum(AICallLog.completion_tokens), 0)
        ).filter(AICallLog.created_at >= since)
        total_cost = db.query(func.coalesce(func.sum(AICallLog.cost_usd), 0)).filter(AICallLog.created_at >= since)
        avg_duration = db.query(func.coalesce(func.avg(duration_seconds(PipelineRun.started_at, PipelineRun.finished_at, db)), 0)).filter(
            PipelineRun.started_at >= since, PipelineRun.status == "completed",
            PipelineRun.started_at.isnot(None), PipelineRun.finished_at.isnot(None),
        )
        cache_hit_steps = db.query(func.count(PipelineStep.id)).filter(
            PipelineStep.cache_key.isnot(None), PipelineStep.status == "skipped", PipelineStep.started_at >= since,
        )
        total_steps = db.query(func.count(PipelineStep.id)).filter(PipelineStep.started_at >= since)
        fmea_active = db.query(func.count(PipelineMetric.id)).filter(PipelineMetric.created_at >= since)

        if project_id is not None:
            run_subq = build_run_subquery(db, project_id)
            total_runs = total_runs.filter(PipelineRun.id.in_(run_subq))
            completed_runs = completed_runs.filter(PipelineRun.id.in_(run_subq))
            total_tokens = total_tokens.filter(AICallLog.run_id.in_(run_subq))
            total_cost = total_cost.filter(AICallLog.run_id.in_(run_subq))
            cache_hit_steps = cache_hit_steps.filter(PipelineStep.run_id.in_(run_subq))
            total_steps = total_steps.filter(PipelineStep.run_id.in_(run_subq))
            metric_subq = db.query(PipelineMetric.id).filter(PipelineMetric.project_id == project_id).subquery().select()
            fmea_active = fmea_active.filter(PipelineMetric.id.in_(metric_subq))

        total_runs_val = total_runs.scalar() or 0
        completed_runs_val = completed_runs.scalar() or 0
        total_tokens_val = int(total_tokens.scalar() or 0)
        total_cost_val = float(total_cost.scalar() or 0)
        avg_duration_val = float(avg_duration.scalar() or 0)
        cache_hit_val = cache_hit_steps.scalar() or 0
        total_steps_val = total_steps.scalar() or 0
        fmea_active_val = fmea_active.scalar() or 0

        cache_hit_rate = (cache_hit_val / total_steps_val * 100) if total_steps_val > 0 else 0.0
        success_rate = (completed_runs_val / total_runs_val * 100) if total_runs_val > 0 else 0.0

        result = {
            "total_runs": total_runs_val, "completed_runs": completed_runs_val,
            "success_rate": round(success_rate, 1), "total_tokens": total_tokens_val,
            "total_cost_usd": round(total_cost_val, 4), "avg_duration_seconds": round(avg_duration_val, 1),
            "cache_hit_rate": round(cache_hit_rate, 1), "fmea_alerts": fmea_active_val, "period_days": days,
        }
        return create_response(data=result, msg="获取成功")
    except Exception as e:
        logger.error("获取仪表盘总览失败: %s", e)
        raise HTTPException(status_code=500, detail="获取仪表盘总览失败，请稍后重试")
