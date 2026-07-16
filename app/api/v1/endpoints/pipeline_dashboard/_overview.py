import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db
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
from app.schemas.common import ApiResponse
from app.services.metrics_service import _date_trunc_day
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Pipeline仪表盘"])


@router.get("/overview", response_model=ApiResponse)
async def get_dashboard_overview(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _overview(sync_db):
        try:
            since = utcnow() - timedelta(days=days)

            # P2-2: 合并 8 次独立 COUNT/SUM/AVG 查询为 4 次（按表分组 + FILTER 子句条件聚合）
            # PipelineRun: total_runs + completed_runs + avg_duration → 1 次查询
            run_stats = sync_db.query(
                func.count(PipelineRun.id).label("total_runs"),
                func.count(PipelineRun.id)
                    .filter(PipelineRun.status == "completed")
                    .label("completed_runs"),
                func.coalesce(
                    func.avg(duration_seconds(PipelineRun.started_at, PipelineRun.finished_at, sync_db))
                        .filter(
                            PipelineRun.status == "completed",
                            PipelineRun.started_at.isnot(None),
                            PipelineRun.finished_at.isnot(None),
                        ),
                    0,
                ).label("avg_duration"),
            ).filter(PipelineRun.started_at >= since)

            # AICallLog: total_tokens + total_cost → 1 次查询
            ai_stats = sync_db.query(
                (
                    func.coalesce(func.sum(AICallLog.prompt_tokens), 0)
                    + func.coalesce(func.sum(AICallLog.completion_tokens), 0)
                ).label("total_tokens"),
                func.coalesce(func.sum(AICallLog.cost_usd), 0).label("total_cost"),
            ).filter(AICallLog.created_at >= since)

            # PipelineStep: cache_hit_steps + total_steps → 1 次查询
            step_stats = sync_db.query(
                func.count(PipelineStep.id)
                    .filter(
                        PipelineStep.cache_key.isnot(None),
                        PipelineStep.status == "skipped",
                    )
                    .label("cache_hit_steps"),
                func.count(PipelineStep.id).label("total_steps"),
            ).filter(PipelineStep.started_at >= since)

            # PipelineMetric: fmea_active → 1 次查询（无合并对象，保持独立）
            fmea_active = sync_db.query(func.count(PipelineMetric.id)).filter(PipelineMetric.created_at >= since)

            if project_id is not None:
                run_subq = build_run_subquery(sync_db, project_id)
                run_stats = run_stats.filter(PipelineRun.id.in_(run_subq))
                ai_stats = ai_stats.filter(AICallLog.run_id.in_(run_subq))
                step_stats = step_stats.filter(PipelineStep.run_id.in_(run_subq))
                metric_subq = sync_db.query(PipelineMetric.id).filter(PipelineMetric.project_id == project_id).subquery().select()
                fmea_active = fmea_active.filter(PipelineMetric.id.in_(metric_subq))

            # 4 次 SQL 往返（原 8 次）
            run_row = run_stats.one()
            ai_row = ai_stats.one()
            step_row = step_stats.one()
            fmea_active_val = fmea_active.scalar() or 0

            total_runs_val = run_row.total_runs or 0
            completed_runs_val = run_row.completed_runs or 0
            avg_duration_val = float(run_row.avg_duration or 0)
            total_tokens_val = int(ai_row.total_tokens or 0)
            total_cost_val = float(ai_row.total_cost or 0)
            cache_hit_val = step_row.cache_hit_steps or 0
            total_steps_val = step_row.total_steps or 0

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

    return await db.run_sync(_overview)
