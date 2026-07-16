"""Pipeline 监控指标 API 端点

提供 FMEA 监控指标的聚合查询和仪表盘摘要功能。

端点:
    GET  /pipeline/metrics/summary    — 仪表盘摘要（所有 FMEA 指标当前值）
    GET  /pipeline/metrics/query      — 聚合查询（按 metric_name 分组统计）
    GET  /pipeline/metrics/timeseries — 时序查询（按天/小时聚合）

迁移说明（任务1 续作 - endpoint async 化）:
    三端点改 async def + AsyncSession + async_get_db，调用 await metrics_service.*
    async 函数。metrics_service.query_metrics / get_metric_timeseries /
    get_dashboard_summary 已迁至 async（详见 metrics_service.py 头部说明）。
"""
import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.services import metrics_service
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Pipeline监控指标"])


@router.get("/summary", response_model=dict)
async def get_metrics_summary(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """获取仪表盘摘要（所有 FMEA 指标的当前值）。"""
    try:
        since = utcnow() - timedelta(days=days)
        result = await metrics_service.get_dashboard_summary(
            db, project_id=project_id, since=since,
        )
        return create_response(data=result, msg="获取成功")
    except Exception as e:
        logger.error("获取监控摘要失败: {}", e)
        raise HTTPException(status_code=500, detail="获取监控摘要失败，请稍后重试")


@router.get("/query", response_model=dict)
async def query_metrics(
    metric_name: Optional[str] = Query(None, description="指标名过滤"),
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    iteration_id: Optional[int] = Query(None, description="迭代 ID 过滤"),
    run_id: Optional[int] = Query(None, description="运行 ID 过滤"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """聚合查询指标（按 metric_name 分组统计 count/sum/avg）。"""
    try:
        since = utcnow() - timedelta(days=days)
        result = await metrics_service.query_metrics(
            db,
            metric_name=metric_name,
            project_id=project_id,
            iteration_id=iteration_id,
            run_id=run_id,
            since=since,
        )
        return create_response(data=result, msg="获取成功")
    except Exception as e:
        logger.error("查询监控指标失败: {}", e)
        raise HTTPException(status_code=500, detail="查询监控指标失败，请稍后重试")


@router.get("/timeseries", response_model=dict)
async def get_metric_timeseries(
    metric_name: str = Query(..., description="指标名（必填）"),
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    interval: str = Query("day", pattern="^(day|hour)$", description="聚合间隔: day/hour"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """时序查询指标（按天/小时聚合，用于仪表盘绘图）。"""
    try:
        since = utcnow() - timedelta(days=days)
        result = await metrics_service.get_metric_timeseries(
            db,
            metric_name=metric_name,
            project_id=project_id,
            since=since,
            interval=interval,
        )
        return create_response(data=result, msg="获取成功")
    except Exception as e:
        logger.error("获取时序数据失败: {}", e)
        raise HTTPException(status_code=500, detail="获取时序数据失败，请稍后重试")
