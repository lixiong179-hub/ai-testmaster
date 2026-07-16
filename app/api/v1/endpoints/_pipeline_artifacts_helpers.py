"""pipeline_artifacts 端点共享常量与工具函数。

包含 payload 截断、取消权限校验、版本重跑指标记录等纯工具逻辑，
供路由处理函数与外部模块复用。
"""
import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from loguru import logger

from app.models.user import User
from app.models.pipeline import PipelineRun

PAYLOAD_TRUNCATE_THRESHOLD = 10 * 1024  # 10KB 截断阈值


def _truncate_payload(payload: Any) -> tuple[Any, bool, Optional[str]]:
    """截断大 payload，超过阈值时仅保留前 N 条并标记截断。

    Args:
        payload: 原始 payload 数据。

    Returns:
        (截断后的 payload, 是否截断, 截断原因)
    """
    raw_size = len(json.dumps(payload, default=str).encode("utf-8"))
    if raw_size <= PAYLOAD_TRUNCATE_THRESHOLD:
        return payload, False, None

    if isinstance(payload, list):
        max_items = 50
        truncated = payload[:max_items]
        reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，仅展示前 {max_items} 条"
        return truncated, True, reason

    if isinstance(payload, dict):
        max_keys = 50
        truncated = dict(list(payload.items())[:max_keys])
        reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，仅展示前 {max_keys} 个键"
        return truncated, True, reason

    if isinstance(payload, str):
        max_chars = PAYLOAD_TRUNCATE_THRESHOLD
        truncated = payload[:max_chars]
        reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，仅展示前 {max_chars} 字符"
        return truncated, True, reason

    reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，类型不可截断"
    return None, True, reason


CANCELLABLE_STATUSES = {"running", "waiting_for_user", "pending"}


def _check_cancel_permission(
    db: Session, run: PipelineRun, current_user: User,
) -> None:
    """校验当前用户是否有权取消指定 Pipeline 运行。

    权限规则：
        - admin 拥有 pipeline:cancel:all，可取消任意运行。
        - qa_lead 拥有 pipeline:cancel:own，仅可取消自己发起的运行。
        - 其他角色无 cancel 权限，返回 403。

    Args:
        db: 数据库会话。
        run: PipelineRun 记录。
        current_user: 当前登录用户。

    Raises:
        HTTPException: 403 无权限。
    """
    from app.services.pipeline_permission_service import check_pipeline_permission
    from app.models.iteration import Iteration

    iteration = db.query(Iteration).filter(Iteration.id == run.iteration_id).first()
    project_id = iteration.project_id if iteration else None

    if check_pipeline_permission(
        db, current_user.id, "pipeline", "cancel", "own", project_id=project_id,
    ):
        has_all_scope = check_pipeline_permission(
            db, current_user.id, "pipeline", "cancel", "all", project_id=project_id,
        )
        if has_all_scope:
            return
        if run.triggered_by == current_user.id:
            return
        raise HTTPException(status_code=403, detail="仅可取消自己发起的 Pipeline 运行")
    raise HTTPException(status_code=403, detail="缺少 pipeline:cancel 权限")


def record_version_rerun_metric(
    db: Session,
    iteration_id: Optional[int] = None,
    detail: Optional[dict] = None,
) -> None:
    """记录 F14 Pipeline 版本升级强制重跑指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        record_metric(
            "pipeline_version_rerun",
            iteration_id=iteration_id,
            detail=detail,
        )
    except Exception as e:
        logger.debug("记录pipeline版本重跑指标失败(不影响业务): %s", e)
