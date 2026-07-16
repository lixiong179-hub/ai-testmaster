import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db
from app.models.user import User
from app.models.pipeline import PipelineRun, PipelineStep
from app.ai.call_log import AICallLog
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.services.metrics_service import _date_trunc_day
from app.utils.db_time import utcnow
from app.api.v1.endpoints.pipeline_dashboard._utils import (
    duration_seconds,
    build_run_subquery,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/token-usage", response_model=dict)
async def get_token_usage(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _token_usage(sync_db):
        try:
            since = utcnow() - timedelta(days=days)
            date_expr = _date_trunc_day(AICallLog.created_at, sync_db)
            query = (
                sync_db.query(
                    date_expr.label("date"),
                    func.coalesce(func.sum(AICallLog.prompt_tokens), 0).label("prompt_tokens"),
                    func.coalesce(func.sum(AICallLog.completion_tokens), 0).label("completion_tokens"),
                    func.coalesce(func.sum(AICallLog.cost_usd), 0).label("cost_usd"),
                )
                .filter(AICallLog.created_at >= since)
                .group_by("date")
                .order_by("date")
            )
            if project_id is not None:
                run_subq = build_run_subquery(sync_db, project_id)
                query = query.filter(AICallLog.run_id.in_(run_subq))
            rows = query.all()
            result = [
                {
                    "date": row.date, "prompt_tokens": int(row.prompt_tokens),
                    "completion_tokens": int(row.completion_tokens),
                    "total_tokens": int(row.prompt_tokens + row.completion_tokens),
                    "cost_usd": float(row.cost_usd),
                }
                for row in rows
            ]
            return create_response(data=result, msg="获取成功")
        except Exception as e:
            logger.error("获取Token消耗失败: %s", e)
            raise HTTPException(status_code=500, detail="获取Token消耗失败，请稍后重试")

    return await db.run_sync(_token_usage)


@router.get("/run-duration", response_model=dict)
async def get_run_duration(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _run_duration(sync_db):
        try:
            since = utcnow() - timedelta(days=days)
            date_expr = _date_trunc_day(PipelineRun.started_at, sync_db)
            duration_expr = duration_seconds(PipelineRun.started_at, PipelineRun.finished_at, sync_db)
            query = (
                sync_db.query(
                    date_expr.label("date"),
                    func.count(PipelineRun.id).label("run_count"),
                    func.coalesce(func.avg(duration_expr), 0).label("avg_duration"),
                    func.coalesce(func.max(duration_expr), 0).label("max_duration"),
                    func.coalesce(func.min(duration_expr), 0).label("min_duration"),
                )
                .filter(PipelineRun.started_at >= since, PipelineRun.status == "completed",
                        PipelineRun.started_at.isnot(None), PipelineRun.finished_at.isnot(None))
                .group_by("date").order_by("date")
            )
            if project_id is not None:
                from app.models.iteration import Iteration
                query = query.join(Iteration, PipelineRun.iteration_id == Iteration.id).filter(Iteration.project_id == project_id)
            rows = query.all()
            result = [
                {
                    "date": row.date, "run_count": row.run_count,
                    "avg_duration_seconds": round(float(row.avg_duration), 1),
                    "max_duration_seconds": round(float(row.max_duration), 1),
                    "min_duration_seconds": round(float(row.min_duration), 1),
                }
                for row in rows
            ]
            return create_response(data=result, msg="获取成功")
        except Exception as e:
            logger.error("获取运行时长失败: %s", e)
            raise HTTPException(status_code=500, detail="获取运行时长失败，请稍后重试")

    return await db.run_sync(_run_duration)


@router.get("/step-latency", response_model=dict)
async def get_step_latency(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _step_latency(sync_db):
        try:
            since = utcnow() - timedelta(days=days)
            duration_expr = duration_seconds(PipelineStep.started_at, PipelineStep.finished_at, sync_db)
            query = (
                sync_db.query(
                    PipelineStep.step_name,
                    func.count(PipelineStep.id).label("count"),
                    func.coalesce(func.avg(duration_expr), 0).label("avg_duration"),
                    func.coalesce(func.max(duration_expr), 0).label("max_duration"),
                    func.coalesce(func.sum(case((PipelineStep.status == "skipped", 1), else_=0)), 0).label("skipped_count"),
                )
                .filter(PipelineStep.started_at >= since, PipelineStep.started_at.isnot(None), PipelineStep.finished_at.isnot(None))
                .group_by(PipelineStep.step_name).order_by(PipelineStep.step_name)
            )
            if project_id is not None:
                run_subq = build_run_subquery(sync_db, project_id)
                query = query.filter(PipelineStep.run_id.in_(run_subq))
            rows = query.all()
            result = [
                {
                    "step_name": row.step_name, "count": row.count,
                    "avg_duration_seconds": round(float(row.avg_duration), 1),
                    "max_duration_seconds": round(float(row.max_duration), 1),
                    "skipped_count": int(row.skipped_count),
                    "skip_rate": round(int(row.skipped_count) / row.count * 100, 1) if row.count > 0 else 0.0,
                }
                for row in rows
            ]
            return create_response(data=result, msg="获取成功")
        except Exception as e:
            logger.error("获取Step耗时失败: %s", e)
            raise HTTPException(status_code=500, detail="获取Step耗时失败，请稍后重试")

    return await db.run_sync(_step_latency)


@router.get("/cache-hit-rate", response_model=dict)
async def get_cache_hit_rate(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _cache_hit_rate(sync_db):
        try:
            since = utcnow() - timedelta(days=days)
            date_expr = _date_trunc_day(PipelineStep.started_at, sync_db)
            query = (
                sync_db.query(
                    date_expr.label("date"),
                    func.count(PipelineStep.id).label("total_steps"),
                    func.coalesce(func.sum(case((PipelineStep.status == "skipped", 1), else_=0)), 0).label("skipped_steps"),
                )
                .filter(PipelineStep.started_at >= since)
                .group_by("date").order_by("date")
            )
            if project_id is not None:
                run_subq = build_run_subquery(sync_db, project_id)
                query = query.filter(PipelineStep.run_id.in_(run_subq))
            rows = query.all()
            result = [
                {
                    "date": row.date, "total_steps": row.total_steps,
                    "skipped_steps": int(row.skipped_steps),
                    "cache_hit_rate": round(int(row.skipped_steps) / row.total_steps * 100, 1) if row.total_steps > 0 else 0.0,
                }
                for row in rows
            ]
            return create_response(data=result, msg="获取成功")
        except Exception as e:
            logger.error("获取缓存命中率失败: %s", e)
            raise HTTPException(status_code=500, detail="获取缓存命中率失败，请稍后重试")

    return await db.run_sync(_cache_hit_rate)
