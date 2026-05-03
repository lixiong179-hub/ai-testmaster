"""
Pipeline 权限模型模块

本模块定义 Pipeline 专用权限体系的数据库模型，与通用 RBAC 并行。
通用 RBAC 管理平台基础权限，Pipeline RBAC 管理流水线相关权限。

核心类概览：
    - PipelineRole : Pipeline 专用角色（admin/qa_lead/qa_engineer/viewer）
    - PipelinePermission : Pipeline 专用权限（resource + action + scope）
    - pipeline_user_role : 用户-角色关联表

角色定义：
    - admin : 全部权限
    - qa_lead : 迭代负责人权限（创建迭代、启动流水线、定稿评审）
    - qa_engineer : 评审者权限（评审用例、查看报告）
    - viewer : 只读权限（查看用例、查看报告）

权限 scope：
    - own : 仅自己创建的
    - project : 项目范围
    - all : 全局

依赖关系：
    - app.db.database.Base : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Index, DateTime, Table
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


pipeline_user_role = Table(
    "pipeline_user_role", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role_id", Integer, ForeignKey("pipeline_roles.id", ondelete="CASCADE"), nullable=False),
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime, nullable=False, default=utcnow),
    UniqueConstraint("user_id", "role_id", "project_id", name="uq_pipeline_user_role"),
    Index("ix_pipeline_user_role_user", "user_id"),
    Index("ix_pipeline_user_role_project", "project_id"),
)


class PipelineRole(Base):
    """Pipeline 专用角色。

    name 枚举: admin, qa_lead, qa_engineer, viewer
    """
    __tablename__ = "pipeline_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(
        String(32), nullable=False, unique=True,
        comment="角色名: admin/qa_lead/qa_engineer/viewer",
    )
    description = Column(String(256), nullable=True, comment="角色描述")
    created_at = Column(DateTime, nullable=False, default=utcnow)

    permissions = relationship("PipelinePermission", back_populates="role", lazy="selectin")
    users = relationship(
        "User", secondary=pipeline_user_role, backref="pipeline_roles", lazy="dynamic",
    )


class PipelinePermission(Base):
    """Pipeline 专用权限。

    resource 枚举: iteration, pipeline, review, test_case, report, config
    action 枚举: create, read, update, delete, start, approve, reject, finalize, cancel
    scope 枚举: own, project, all
    """
    __tablename__ = "pipeline_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(
        Integer, ForeignKey("pipeline_roles.id", ondelete="CASCADE"), nullable=False,
    )
    resource = Column(String(32), nullable=False, comment="资源类型")
    action = Column(String(32), nullable=False, comment="操作类型")
    scope = Column(String(16), nullable=False, default="project", comment="范围: own/project/all")

    role = relationship("PipelineRole", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "resource", "action", "scope", name="uq_pipeline_permission"),
        Index("ix_pipeline_permission_role", "role_id"),
    )
