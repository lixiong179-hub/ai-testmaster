"""
业务能力模型模块

本模块定义了业务能力（TestCapability）模型，作为测试体系中最稳定的层级实体。
所有 TestPoint 必须挂在某个 Capability 下，Capability 代表系统的一个独立业务能力单元。

核心类概览：
    - TestCapability : 业务能力模型，同项目内 key 唯一

表关系：
    Project → TestCapability（一对多，级联删除）
    TestCapability → TestPoint（一对多，SET NULL，能力删除后测试点保留）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base
from app.models.enums import CapabilityStatus


class TestCapability(Base):
    """
    业务能力模型 - 测试体系最稳定层级实体

    Capability 代表系统的一个独立业务能力单元（如"用户管理"、"订单处理"），
    是 TestPoint 的上层归类。UI 变更不影响 Capability，只有业务重组时才变更。

    不变式（plan §3.2）：
        - 同项目内 key 唯一
        - UI 改不影响它
        - status 只能通过 LifecycleService 变更

    表关系：
        - 多对一 → Project（所属项目，级联删除）
        - 一对多 → TestPoint（关联测试点，SET NULL）
    """
    __test__ = False
    __tablename__ = "test_capabilities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联项目ID，多项目隔离核心"
    )
    key = Column(
        String(100),
        nullable=False,
        comment="能力唯一标识，同项目内唯一，如 'user_management'"
    )
    title = Column(
        String(255),
        nullable=False,
        comment="能力显示名称，如 '用户管理'"
    )
    description = Column(
        Text,
        nullable=True,
        comment="能力描述，说明该能力涵盖的业务范围"
    )
    status = Column(
        String(20),
        nullable=False,
        default=CapabilityStatus.ACTIVE.value,
        comment="能力状态：active/deprecated/archived"
    )
    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_test_capability_project_key"),
        Index("ix_test_capability_project_status", "project_id", "status"),
    )

    # 关联关系
    project = relationship("Project", back_populates="test_capabilities")
    test_points = relationship("TestPoint", back_populates="capability", foreign_keys="TestPoint.capability_id")
