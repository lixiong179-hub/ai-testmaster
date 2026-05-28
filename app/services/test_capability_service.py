"""
业务能力 CRUD 服务

提供 TestCapability 的增删改查操作。删除操作通过 LifecycleService 走 archived 软删除。
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.test_capability import TestCapability
from app.models.enums import CapabilityStatus
from app.services.lifecycle_service import transition_capability


class DuplicateCapabilityKeyError(Exception):
    """同项目下 key 重复"""
    pass


def create_capability(
    db: Session,
    project_id: int,
    key: str,
    title: str,
    description: Optional[str] = None,
    status: str = "active",
) -> TestCapability:
    """创建业务能力"""
    capability = TestCapability(
        project_id=project_id,
        key=key,
        title=title,
        description=description,
        status=status,
    )
    db.add(capability)
    try:
        db.flush()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise DuplicateCapabilityKeyError(
            f"Capability key '{key}' already exists in project {project_id}"
        ) from e
    db.refresh(capability)
    return capability


def get_capability_by_id(db: Session, capability_id: int) -> Optional[TestCapability]:
    """按 ID 获取能力"""
    return db.query(TestCapability).filter(TestCapability.id == capability_id).first()


def get_capabilities_by_project(
    db: Session,
    project_id: int,
    status: Optional[str] = None,
    include_archived: bool = False,
) -> List[TestCapability]:
    """按项目列出能力，可选按 status 过滤。

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        status: 按状态精确过滤（可选）。
        include_archived: 是否包含已归档能力，默认 False。

    Returns:
        符合条件的能力列表，按 key 排序。
    """
    query = db.query(TestCapability).filter(TestCapability.project_id == project_id)
    if not include_archived:
        query = query.filter(TestCapability.status != CapabilityStatus.ARCHIVED.value)
    if status is not None:
        query = query.filter(TestCapability.status == status)
    return query.order_by(TestCapability.key).all()


_UNSET = object()  # 哨兵值，区分"未传入"和"显式传 None"


def update_capability(
    db: Session,
    capability_id: int,
    **kwargs,
) -> Optional[TestCapability]:
    """更新能力字段，支持将可选字段清空为 None（显式传 None）"""
    capability = get_capability_by_id(db, capability_id)
    if capability is None:
        return None
    for field, value in kwargs.items():
        if value is not _UNSET and hasattr(capability, field):
            setattr(capability, field, value)
    try:
        db.flush()
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise DuplicateCapabilityKeyError(
            "Capability key conflict after update"
        ) from e
    db.refresh(capability)
    return capability


def delete_capability(
    db: Session,
    capability_id: int,
    *,
    actor_id: Optional[int] = None,
) -> Optional[TestCapability]:
    """软删除能力：将 status 置为 archived。

    Args:
        db: 数据库会话。
        capability_id: 目标能力 ID。
        actor_id: 操作人 ID（可选）。

    Returns:
        归档后的 TestCapability 实例；能力不存在时返回 None。
    """
    capability = get_capability_by_id(db, capability_id)
    if capability is None:
        return None
    if capability.status == CapabilityStatus.ARCHIVED.value:
        return capability
    return transition_capability(
        db,
        capability_id,
        CapabilityStatus.ARCHIVED.value,
        actor_id=actor_id,
    )
