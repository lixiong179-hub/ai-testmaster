"""
Capability 生命周期服务

提供 TestCapability 状态流转与审计日志记录。
状态变更必须通过本模块，禁止直接 SQL UPDATE status 字段。
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.test_capability import TestCapability
from app.services.lifecycle_service._capability_rules import (
    _CAPABILITY_VALID_TRANSITIONS,
    IllegalCapabilityTransition,
)

logger = logging.getLogger(__name__)


def can_transition_capability(fromStatus: str, toStatus: str) -> bool:
    """判断 Capability 是否允许从 fromStatus 转换到 toStatus。

    Args:
        fromStatus: 当前状态值。
        toStatus: 目标状态值。

    Returns:
        合法返回 True，否则 False。
    """
    return toStatus in _CAPABILITY_VALID_TRANSITIONS.get(fromStatus, set())


def transition_capability(
    db: Session,
    capability_id: int,
    toStatus: str,
    *,
    actor_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> TestCapability:
    """执行 Capability 状态流转并写入审计日志。

    Args:
        db: 数据库会话。
        capability_id: 目标能力 ID。
        toStatus: 目标状态值。
        actor_id: 操作人 ID（可选）。
        reason: 变更原因（可选）。

    Returns:
        状态更新后的 TestCapability 实例。

    Raises:
        ValueError: capability 不存在。
        IllegalCapabilityTransition: 状态流转不合法。
    """
    capability = db.query(TestCapability).filter(
        TestCapability.id == capability_id
    ).first()
    if capability is None:
        raise ValueError(f"TestCapability id={capability_id} not found")

    fromStatus = capability.status
    if not can_transition_capability(fromStatus, toStatus):
        raise IllegalCapabilityTransition(fromStatus, toStatus)

    oldStatus = fromStatus
    capability.status = toStatus
    db.flush()

    _write_capability_audit_log(
        db=db,
        capability_id=capability_id,
        oldStatus=oldStatus,
        newStatus=toStatus,
        actor_id=actor_id,
        reason=reason,
    )

    db.commit()

    return capability


def _resolve_capability_action(oldStatus: str, newStatus: str) -> str:
    """根据状态流转方向确定审计日志 action。"""
    if newStatus == "archived":
        return "capability_archive"
    if newStatus == "deprecated":
        return "capability_deprecate"
    return "capability_status_change"


def _write_capability_audit_log(
    db: Session,
    capability_id: int,
    oldStatus: str,
    newStatus: str,
    actor_id: Optional[int],
    reason: Optional[str],
) -> None:
    """写入 Capability 状态变更审计日志。"""
    detail: dict = {"from": oldStatus, "to": newStatus}
    if reason is not None:
        detail["reason"] = reason

    action = _resolve_capability_action(oldStatus, newStatus)

    try:
        from app.services.audit_service import log_action
        log_action(
            db=db,
            action=action,
            actor_id=actor_id,
            target_kind="test_capability",
            target_id=capability_id,
            detail=detail,
        )
    except Exception as e:
        logger.error(
            "Failed to write audit log for %s: "
            "capability_id=%d, %s -> %s, error=%s",
            action, capability_id, oldStatus, newStatus, e,
        )
