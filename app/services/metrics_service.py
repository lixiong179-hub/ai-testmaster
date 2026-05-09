"""
Pipeline 监控指标服务模块

本模块提供 FMEA 监控指标的记录和聚合查询功能。
对应 plan §8 FMEA 表中 F1/F2/F3/F5/F9/F11/F12/F13/F14/F15 各项。

核心函数概览：
    - record_metric   : 记录单条监控指标
    - record_metrics  : 批量记录监控指标
    - query_metrics   : 聚合查询指标（按 metric_name 分组统计）
    - get_metric_timeseries : 时序查询指标（用于仪表盘绘图）

依赖关系：
    - app.models.pipeline_metric : PipelineMetric, VALID_METRIC_NAMES
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from loguru import logger

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.pipeline_metric import PipelineMetric, VALID_METRIC_NAMES, FMEA_METRICS


def record_metric(
    metric_name: str,
    *,
    value: float = 1.0,
    project_id: Optional[int] = None,
    iteration_id: Optional[int] = None,
    run_id: Optional[int] = None,
    step_name: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Optional[PipelineMetric]:
    """记录单条监控指标（使用独立 Session 提交，不随主事务回滚丢失）。

    Args:
        metric_name: 指标名（必须为 VALID_METRIC_NAMES 中的值）。
        value: 指标值（默认 1.0，用于计数）。
        project_id: 项目 ID。
        iteration_id: 迭代 ID。
        run_id: PipelineRun ID。
        step_name: Step 名称。
        detail: 附加详情。

    Returns:
        创建后的 PipelineMetric 实例，失败返回 None。

    Raises:
        ValueError: metric_name 不在合法枚举中。
    """
    if metric_name not in VALID_METRIC_NAMES:
        raise ValueError(
            f"Invalid metric name: '{metric_name}'. "
            f"Valid names: {sorted(VALID_METRIC_NAMES)}"
        )

    record = PipelineMetric(
        metric_name=metric_name,
        value=value,
        project_id=project_id,
        iteration_id=iteration_id,
        run_id=run_id,
        step_name=step_name,
        detail=detail,
    )
    try:
        from app.db.database import get_db_context
        with get_db_context() as db:
            db.add(record)
            db.flush()
            db.expunge(record)
        return record
    except Exception as e:
        logger.debug(f"指标记录失败: {e}")
        return None


def record_metrics(
    metrics: List[Dict[str, Any]],
) -> List[PipelineMetric]:
    """批量记录监控指标（使用独立 Session 提交）。

    Args:
        metrics: 指标字典列表，每个字典含 metric_name 及可选字段。

    Returns:
        创建后的 PipelineMetric 实例列表。
    """
    results = []
    for m in metrics:
        name = m.get("metric_name", "")
        if name not in VALID_METRIC_NAMES:
            continue
        result = record_metric(
            name,
            value=m.get("value", 1.0),
            project_id=m.get("project_id"),
            iteration_id=m.get("iteration_id"),
            run_id=m.get("run_id"),
            step_name=m.get("step_name"),
            detail=m.get("detail"),
        )
        if result is not None:
            results.append(result)
    return results


def query_metrics(
    db: Session,
    *,
    metric_name: Optional[str] = None,
    project_id: Optional[int] = None,
    iteration_id: Optional[int] = None,
    run_id: Optional[int] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """聚合查询指标（按 metric_name 分组统计 count/sum/avg）。

    Args:
        db: 数据库会话。
        metric_name: 按指标名过滤（可选）。
        project_id: 按项目过滤（可选）。
        iteration_id: 按迭代过滤（可选）。
        run_id: 按运行过滤（可选）。
        since: 起始时间（含）。
        until: 截止时间（含）。

    Returns:
        聚合结果列表，每项含 metric_name, count, total, avg_value, fmea_id, description。
    """
    filters = _build_filters(
        metric_name=metric_name,
        project_id=project_id,
        iteration_id=iteration_id,
        run_id=run_id,
        since=since,
        until=until,
    )

    rows = (
        db.query(
            PipelineMetric.metric_name,
            func.count(PipelineMetric.id).label("count"),
            func.coalesce(func.sum(PipelineMetric.value), 0).label("total"),
            func.coalesce(func.avg(PipelineMetric.value), 0).label("avg_value"),
        )
        .filter(and_(*filters) if filters else True)
        .group_by(PipelineMetric.metric_name)
        .all()
    )

    results = []
    for row in rows:
        meta = FMEA_METRICS.get(row.metric_name, {})
        results.append({
            "metric_name": row.metric_name,
            "fmea_id": meta.get("fmea_id", ""),
            "description": meta.get("description", ""),
            "count": row.count,
            "total": float(row.total),
            "avg_value": round(float(row.avg_value), 4),
        })
    return results


def get_metric_timeseries(
    db: Session,
    metric_name: str,
    *,
    project_id: Optional[int] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    interval: str = "day",
) -> List[Dict[str, Any]]:
    """时序查询指标（按天/小时聚合，用于仪表盘绘图）。

    Args:
        db: 数据库会话。
        metric_name: 指标名。
        project_id: 按项目过滤（可选）。
        since: 起始时间（含）。
        until: 截止时间（含）。
        interval: 聚合间隔（day/hour）。

    Returns:
        时序数据列表，每项含 time_bucket, count, total。
    """
    filters = _build_filters(
        metric_name=metric_name,
        project_id=project_id,
        since=since,
        until=until,
    )

    if interval == "hour":
        date_expr = _date_trunc_hour(PipelineMetric.created_at, db)
    else:
        date_expr = _date_trunc_day(PipelineMetric.created_at, db)

    rows = (
        db.query(
            date_expr.label("time_bucket"),
            func.count(PipelineMetric.id).label("count"),
            func.coalesce(func.sum(PipelineMetric.value), 0).label("total"),
        )
        .filter(and_(*filters) if filters else True)
        .group_by("time_bucket")
        .order_by("time_bucket")
        .all()
    )

    return [
        {
            "time_bucket": row.time_bucket,
            "count": row.count,
            "total": float(row.total),
        }
        for row in rows
    ]


def get_dashboard_summary(
    db: Session,
    *,
    project_id: Optional[int] = None,
    since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """获取仪表盘摘要（所有 FMEA 指标的当前值）。

    Args:
        db: 数据库会话。
        project_id: 按项目过滤（可选）。
        since: 起始时间（含）。

    Returns:
        摘要字典，含 metrics 列表和 generated_at 时间戳。
    """
    aggregated = query_metrics(
        db, project_id=project_id, since=since,
    )

    all_metrics = []
    for name, meta in FMEA_METRICS.items():
        found = None
        for agg in aggregated:
            if agg["metric_name"] == name:
                found = agg
                break
        all_metrics.append({
            "metric_name": name,
            "fmea_id": meta["fmea_id"],
            "description": meta["description"],
            "count": found["count"] if found else 0,
            "total": found["total"] if found else 0.0,
            "avg_value": found["avg_value"] if found else 0.0,
        })

    return {
        "metrics": all_metrics,
        "total_metric_types": len(FMEA_METRICS),
        "active_metric_types": len([m for m in all_metrics if m["count"] > 0]),
    }


def _build_filters(
    metric_name: Optional[str] = None,
    project_id: Optional[int] = None,
    iteration_id: Optional[int] = None,
    run_id: Optional[int] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> List[Any]:
    """构建查询过滤条件列表。"""
    filters = []
    if metric_name is not None:
        filters.append(PipelineMetric.metric_name == metric_name)
    if project_id is not None:
        filters.append(PipelineMetric.project_id == project_id)
    if iteration_id is not None:
        filters.append(PipelineMetric.iteration_id == iteration_id)
    if run_id is not None:
        filters.append(PipelineMetric.run_id == run_id)
    if since is not None:
        filters.append(PipelineMetric.created_at >= since)
    if until is not None:
        filters.append(PipelineMetric.created_at <= until)
    return filters


def _get_dialect_name(db: Session) -> str:
    """获取当前数据库方言名称。"""
    try:
        return db.bind.dialect.name
    except Exception:
        return "mysql"


def _date_trunc_day(column, db: Session):
    """按天截断日期（跨数据库兼容）。"""
    dialect = _get_dialect_name(db)
    if dialect == "sqlite":
        return func.strftime("%Y-%m-%d", column)
    return func.date_format(column, "%Y-%m-%d")


def _date_trunc_hour(column, db: Session):
    """按小时截断日期（跨数据库兼容）。"""
    dialect = _get_dialect_name(db)
    if dialect == "sqlite":
        return func.strftime("%Y-%m-%d %H:00", column)
    return func.date_format(column, "%Y-%m-%d %H:00")
