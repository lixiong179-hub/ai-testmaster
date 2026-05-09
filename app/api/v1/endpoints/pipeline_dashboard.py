"""Pipeline 成本/性能仪表盘聚合 API 端点

提供 Pipeline 运行成本与性能的可视化数据聚合。

端点:
    GET /pipeline/dashboard/overview       — 总览（关键指标卡片）
    GET /pipeline/dashboard/token-usage    — 每日 AI Token 消耗时序
    GET /pipeline/dashboard/run-duration   — 平均运行时长趋势
    GET /pipeline/dashboard/step-latency   — 各 Step 耗时分布
    GET /pipeline/dashboard/cache-hit-rate — 缓存命中率趋势
"""
import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_, case, Integer, text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.pipeline import PipelineRun, PipelineStep
from app.models.pipeline_metric import PipelineMetric, FMEA_METRICS
from app.ai.call_log import AICallLog
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.services.metrics_service import _date_trunc_day
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline/dashboard", tags=["Pipeline仪表盘"])


def _duration_seconds(start_col, end_col, db: Session):
    """计算两个时间列的秒数差（跨数据库兼容）。

    SQLite: 使用 julianday 计算天数差再转秒
    MySQL:  使用 TIMESTAMPDIFF(SECOND, start, end)
    """
    dialect = _get_dialect_name(db)
    if dialect == "sqlite":
        return (
            func.cast(
                (func.julianday(end_col) - func.julianday(start_col)) * 86400,
                Integer,
            )
        )
    return func.timestampdiff(text("SECOND"), start_col, end_col)


def _get_dialect_name(db: Session) -> str:
    """获取当前数据库方言名称。"""
    try:
        return db.bind.dialect.name
    except Exception:
        return "mysql"


def _build_run_subquery(db: Session, project_id: int):
    """构建按项目过滤的 PipelineRun 子查询（复用逻辑）。"""
    from app.models.iteration import Iteration
    return (
        db.query(PipelineRun.id)
        .join(Iteration, PipelineRun.iteration_id == Iteration.id)
        .filter(Iteration.project_id == project_id)
        .subquery()
        .select()
    )


@router.get("/overview", response_model=dict)
def get_dashboard_overview(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取仪表盘总览（关键指标卡片）。"""
    try:
        since = utcnow() - timedelta(days=days)

        total_runs = (
            db.query(func.count(PipelineRun.id))
            .filter(PipelineRun.started_at >= since)
        )
        completed_runs = (
            db.query(func.count(PipelineRun.id))
            .filter(
                PipelineRun.started_at >= since,
                PipelineRun.status == "completed",
            )
        )
        total_tokens = (
            db.query(func.coalesce(func.sum(AICallLog.prompt_tokens + AICallLog.completion_tokens), 0))
            .filter(AICallLog.created_at >= since)
        )
        total_cost = (
            db.query(func.coalesce(func.sum(AICallLog.cost_usd), 0))
            .filter(AICallLog.created_at >= since)
        )
        avg_duration = (
            db.query(func.coalesce(
                func.avg(_duration_seconds(PipelineRun.started_at, PipelineRun.finished_at, db)), 0))
            .filter(
                PipelineRun.started_at >= since,
                PipelineRun.status == "completed",
                PipelineRun.started_at.isnot(None),
                PipelineRun.finished_at.isnot(None),
            )
        )

        cache_hit_steps = (
            db.query(func.count(PipelineStep.id))
            .filter(
                PipelineStep.cache_key.isnot(None),
                PipelineStep.status == "skipped",
                PipelineStep.started_at >= since,
            )
        )
        total_steps = (
            db.query(func.count(PipelineStep.id))
            .filter(PipelineStep.started_at >= since)
        )

        fmea_active = (
            db.query(func.count(PipelineMetric.id))
            .filter(PipelineMetric.created_at >= since)
        )

        if project_id is not None:
            from app.models.iteration import Iteration
            run_subq = _build_run_subquery(db, project_id)
            total_runs = total_runs.filter(PipelineRun.id.in_(run_subq))
            completed_runs = completed_runs.filter(PipelineRun.id.in_(run_subq))

            call_subq = (
                db.query(AICallLog.id)
                .join(PipelineRun, AICallLog.run_id == PipelineRun.id)
                .join(Iteration, PipelineRun.iteration_id == Iteration.id)
                .filter(Iteration.project_id == project_id)
                .subquery()
                .select()
            )
            total_tokens = total_tokens.filter(AICallLog.id.in_(call_subq))
            total_cost = total_cost.filter(AICallLog.id.in_(call_subq))

            step_subq = (
                db.query(PipelineStep.id)
                .join(PipelineRun, PipelineStep.run_id == PipelineRun.id)
                .join(Iteration, PipelineRun.iteration_id == Iteration.id)
                .filter(Iteration.project_id == project_id)
                .subquery()
                .select()
            )
            cache_hit_steps = cache_hit_steps.filter(PipelineStep.id.in_(step_subq))
            total_steps = total_steps.filter(PipelineStep.id.in_(step_subq))

            metric_subq = (
                db.query(PipelineMetric.id)
                .filter(PipelineMetric.project_id == project_id)
                .subquery()
                .select()
            )
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
            "total_runs": total_runs_val,
            "completed_runs": completed_runs_val,
            "success_rate": round(success_rate, 1),
            "total_tokens": total_tokens_val,
            "total_cost_usd": round(total_cost_val, 4),
            "avg_duration_seconds": round(avg_duration_val, 1),
            "cache_hit_rate": round(cache_hit_rate, 1),
            "fmea_alerts": fmea_active_val,
            "period_days": days,
        }
        return create_response(data=result, msg="获取成功")
    except Exception as e:
        logger.error("获取仪表盘总览失败: %s", e)
        raise HTTPException(status_code=500, detail="获取仪表盘总览失败，请稍后重试")


@router.get("/token-usage", response_model=dict)
def get_token_usage(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取每日 AI Token 消耗时序。"""
    try:
        since = utcnow() - timedelta(days=days)
        date_expr = _date_trunc_day(AICallLog.created_at, db)

        query = (
            db.query(
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
            run_subq = _build_run_subquery(db, project_id)
            query = query.filter(AICallLog.run_id.in_(run_subq))

        rows = query.all()
        result = [
            {
                "date": row.date,
                "prompt_tokens": int(row.prompt_tokens),
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


@router.get("/run-duration", response_model=dict)
def get_run_duration(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取平均运行时长趋势。"""
    try:
        since = utcnow() - timedelta(days=days)
        date_expr = _date_trunc_day(PipelineRun.started_at, db)

        duration_expr = _duration_seconds(PipelineRun.started_at, PipelineRun.finished_at, db)

        query = (
            db.query(
                date_expr.label("date"),
                func.count(PipelineRun.id).label("run_count"),
                func.coalesce(func.avg(duration_expr), 0).label("avg_duration"),
                func.coalesce(func.max(duration_expr), 0).label("max_duration"),
                func.coalesce(func.min(duration_expr), 0).label("min_duration"),
            )
            .filter(
                PipelineRun.started_at >= since,
                PipelineRun.status == "completed",
                PipelineRun.started_at.isnot(None),
                PipelineRun.finished_at.isnot(None),
            )
            .group_by("date")
            .order_by("date")
        )

        if project_id is not None:
            from app.models.iteration import Iteration
            query = query.join(Iteration, PipelineRun.iteration_id == Iteration.id).filter(
                Iteration.project_id == project_id
            )

        rows = query.all()
        result = [
            {
                "date": row.date,
                "run_count": row.run_count,
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


@router.get("/step-latency", response_model=dict)
def get_step_latency(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取各 Step 耗时分布。"""
    try:
        since = utcnow() - timedelta(days=days)
        duration_expr = _duration_seconds(PipelineStep.started_at, PipelineStep.finished_at, db)

        query = (
            db.query(
                PipelineStep.step_name,
                func.count(PipelineStep.id).label("count"),
                func.coalesce(func.avg(duration_expr), 0).label("avg_duration"),
                func.coalesce(func.max(duration_expr), 0).label("max_duration"),
                func.coalesce(func.sum(case((PipelineStep.status == "skipped", 1), else_=0)), 0).label("skipped_count"),
            )
            .filter(
                PipelineStep.started_at >= since,
                PipelineStep.started_at.isnot(None),
                PipelineStep.finished_at.isnot(None),
            )
            .group_by(PipelineStep.step_name)
            .order_by(PipelineStep.step_name)
        )

        if project_id is not None:
            run_subq = _build_run_subquery(db, project_id)
            query = query.filter(PipelineStep.run_id.in_(run_subq))

        rows = query.all()
        result = [
            {
                "step_name": row.step_name,
                "count": row.count,
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


@router.get("/cache-hit-rate", response_model=dict)
def get_cache_hit_rate(
    project_id: Optional[int] = Query(None, description="项目 ID 过滤"),
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取缓存命中率趋势。"""
    try:
        since = utcnow() - timedelta(days=days)
        date_expr = _date_trunc_day(PipelineStep.started_at, db)

        query = (
            db.query(
                date_expr.label("date"),
                func.count(PipelineStep.id).label("total_steps"),
                func.coalesce(func.sum(case((PipelineStep.status == "skipped", 1), else_=0)), 0).label("skipped_steps"),
            )
            .filter(PipelineStep.started_at >= since)
            .group_by("date")
            .order_by("date")
        )

        if project_id is not None:
            run_subq = _build_run_subquery(db, project_id)
            query = query.filter(PipelineStep.run_id.in_(run_subq))

        rows = query.all()
        result = [
            {
                "date": row.date,
                "total_steps": row.total_steps,
                "skipped_steps": int(row.skipped_steps),
                "cache_hit_rate": round(int(row.skipped_steps) / row.total_steps * 100, 1) if row.total_steps > 0 else 0.0,
            }
            for row in rows
        ]
        return create_response(data=result, msg="获取成功")
    except Exception as e:
        logger.error("获取缓存命中率失败: %s", e)
        raise HTTPException(status_code=500, detail="获取缓存命中率失败，请稍后重试")
