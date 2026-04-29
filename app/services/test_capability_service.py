"""
业务能力 CRUD 服务

提供 TestCapability 的增删改查操作。M1 阶段仅服务层，不暴露 API 端点。
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.test_capability import TestCapability


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
) -> List[TestCapability]:
    """按项目列出能力，可选按 status 过滤"""
    query = db.query(TestCapability).filter(TestCapability.project_id == project_id)
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
            f"Capability key conflict after update"
        ) from e
    db.refresh(capability)
    return capability


def delete_capability(db: Session, capability_id: int) -> bool:
    """删除能力（硬删除）。M1 阶段临时方案，后续应由 LifecycleService 走 archived 状态。"""
    capability = get_capability_by_id(db, capability_id)
    if capability is None:
        return False
    db.delete(capability)
    db.commit()
    return True
