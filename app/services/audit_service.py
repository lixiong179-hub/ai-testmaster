"""
审计日志服务模块

本模块提供不可变审计日志的写入和查询功能。
所有关键操作必须通过此服务记录，禁止直接 SQL INSERT。

核心函数概览：
    - log_action : 写入审计日志（不可变、仅追加）
    - query_logs : 查询审计日志（支持多维度过滤+分页）

依赖关系：
    - app.models.audit_log : AuditLog
"""
from typing import Optional, List
from loguru import logger
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.audit_log import AuditLog


VALID_ACTIONS = {
    "lifecycle_transition",
    "review_decide",
    "review_rollback",
    "review_undo",
    "review_finalize",
    "pipeline_start",
    "pipeline_step_complete",
    "pipeline_pause",
    "pipeline_resume",
    "pipeline_cancel",
    "permission_change",
    "config_change",
    "case_version_create",
    "locator_version_create",
    "force_cancel_review",
}


def log_action(
    db: Session,
    action: str,
    actor_id: Optional[int],
    target_kind: str,
    target_id: int,
    *,
    detail: Optional[dict] = None,
    run_id: Optional[int] = None,
    iteration_id: Optional[int] = None,
) -> AuditLog:
    """写入审计日志。

    Args:
        db: 数据库会话。
        action: 操作类型（必须为 VALID_ACTIONS 中的值）。
        actor_id: 操作人 ID。
        target_kind: 目标实体类型。
        target_id: 目标实体 ID。
        detail: 变更详情（如 {"from": "active", "to": "deprecated"}）。
        run_id: 关联 PipelineRun ID（可选）。
        iteration_id: 关联迭代 ID（可选）。

    Returns:
        创建后的 AuditLog 实例。

    Raises:
        ValueError: action 不在合法枚举中。
    """
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Invalid audit action: '{action}'. "
            f"Valid actions: {sorted(VALID_ACTIONS)}"
        )

    record = AuditLog(
        action=action,
        actor_id=actor_id,
        target_kind=target_kind,
        target_id=target_id,
        detail=detail,
        run_id=run_id,
        iteration_id=iteration_id,
    )
    db.add(record)
    try:
        db.flush()
    except Exception as e:
        _record_audit_failure_metric(action, str(e)[:200])
        raise
    return record


def _build_filters(
    target_kind: Optional[str] = None,
    target_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list:
    """构建审计日志查询过滤条件。"""
    filters = []
    if target_kind is not None:
        filters.append(AuditLog.target_kind == target_kind)
    if target_id is not None:
        filters.append(AuditLog.target_id == target_id)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if action is not None:
        filters.append(AuditLog.action == action)
    if since is not None:
        filters.append(AuditLog.created_at >= since)
    if until is not None:
        filters.append(AuditLog.created_at <= until)
    return filters


def query_logs(
    db: Session,
    *,
    target_kind: Optional[str] = None,
    target_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[AuditLog]:
    """查询审计日志（支持多维度过滤+分页）。

    Args:
        db: 数据库会话。
        target_kind: 按目标实体类型过滤。
        target_id: 按目标实体 ID 过滤。
        actor_id: 按操作人过滤。
        action: 按操作类型过滤。
        since: 起始时间（含）。
        until: 截止时间（含）。
        limit: 返回上限（默认 100，最大 500）。
        offset: 分页偏移。

    Returns:
        AuditLog 列表（按 created_at 倒序）。
    """
    limit = min(limit, 500)
    filters = _build_filters(target_kind, target_id, actor_id, action, since, until)

    return (
        db.query(AuditLog)
        .filter(and_(*filters) if filters else True)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_logs(
    db: Session,
    *,
    target_kind: Optional[str] = None,
    target_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> int:
    """统计审计日志条数（用于分页计算）。

    Args:
        db: 数据库会话。
        target_kind: 按目标实体类型过滤。
        target_id: 按目标实体 ID 过滤。
        actor_id: 按操作人过滤。
        action: 按操作类型过滤。
        since: 起始时间（含）。
        until: 截止时间（含）。

    Returns:
        符合条件的日志条数。
    """
    filters = _build_filters(target_kind, target_id, actor_id, action, since, until)

    return (
        db.query(AuditLog)
        .filter(and_(*filters) if filters else True)
        .count()
    )


def _record_audit_failure_metric(action: str, error_snippet: str) -> None:
    """记录 F15 审计日志写入失败指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        record_metric(
            "audit_log_write_failure",
            detail={"action": action, "error": error_snippet},
        )
    except Exception as e:
        logger.debug(f"审计指标记录失败(不影响业务): {e}")
