import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, and_, select

from app.db.database import async_get_db
from sqlalchemy.ext.asyncio import AsyncSession
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
    try:
        since = utcnow() - timedelta(days=days)

        # P2-2: 合并 8 次独立 COUNT/SUM/AVG 查询为 4 次（按表分组 + CASE WHEN 条件聚合）
        # 注意：MySQL 不支持 PostgreSQL 的 FILTER (WHERE ...) 语法，使用 SUM(CASE WHEN ...) 替代
        # PipelineRun: total_runs + completed_runs + avg_duration → 1 次查询
        run_stmt = select(
            func.count(PipelineRun.id).label("total_runs"),
            func.sum(
                case((PipelineRun.status == "completed", 1), else_=0)
            ).label("completed_runs"),
            func.coalesce(
                func.avg(
                    case(
                        (
                            and_(
                                PipelineRun.status == "completed",
                                PipelineRun.started_at.isnot(None),
                                PipelineRun.finished_at.isnot(None),
                            ),
                            duration_seconds(PipelineRun.started_at, PipelineRun.finished_at, db),
                        ),
                        else_=None,
                    )
                ),
                0,
            ).label("avg_duration"),
        ).where(PipelineRun.started_at >= since)

        # AICallLog: total_tokens + total_cost → 1 次查询
        ai_stmt = select(
            (
                func.coalesce(func.sum(AICallLog.prompt_tokens), 0)
                + func.coalesce(func.sum(AICallLog.completion_tokens), 0)
            ).label("total_tokens"),
            func.coalesce(func.sum(AICallLog.cost_usd), 0).label("total_cost"),
        ).where(AICallLog.created_at >= since)

        # PipelineStep: cache_hit_steps + total_steps → 1 次查询
        step_stmt = select(
            func.sum(
                case(
                    (
                        and_(
                            PipelineStep.cache_key.isnot(None),
                            PipelineStep.status == "skipped",
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("cache_hit_steps"),
            func.count(PipelineStep.id).label("total_steps"),
        ).where(PipelineStep.started_at >= since)

        # PipelineMetric: fmea_active → 1 次查询（无合并对象，保持独立）
        fmea_stmt = select(func.count(PipelineMetric.id)).where(PipelineMetric.created_at >= since)

        if project_id is not None:
            run_subq = build_run_subquery(db, project_id)
            run_stmt = run_stmt.where(PipelineRun.id.in_(run_subq))
            ai_stmt = ai_stmt.where(AICallLog.run_id.in_(run_subq))
            step_stmt = step_stmt.where(PipelineStep.run_id.in_(run_subq))
            metric_subq = (
                select(PipelineMetric.id)
                .where(PipelineMetric.project_id == project_id)
                .subquery()
                .select()
            )
            fmea_stmt = fmea_stmt.where(PipelineMetric.id.in_(metric_subq))

        # 4 次 SQL 往返（原 8 次）
        run_row = (await db.execute(run_stmt)).one()
        ai_row = (await db.execute(ai_stmt)).one()
        step_row = (await db.execute(step_stmt)).one()
        fmea_active_val = (await db.execute(fmea_stmt)).scalar() or 0

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
