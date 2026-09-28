"""项目成员模型模块。

定义 ProjectMember 模型，支持项目级多角色成员体系（owner/admin/member/viewer），
替代原有单一的 Project.user_id 属主校验，实现细粒度项目权限控制。

核心类概览：
    - ProjectMember : 项目成员关联模型，存储用户在项目中的角色

表关系：
    Project ←→ User（多对多，通过 project_members 关联表）
    ProjectMember.role 定义成员角色层级：owner > admin > member > viewer

角色层级（ROLE_LEVEL）：
    - owner  (4) : 项目所有者，拥有全部权限包括删除项目和转让所有权
    - admin  (3) : 项目管理员，可管理成员、编辑项目配置、执行所有测试操作
    - member (2) : 项目成员，可创建/编辑测试用例、执行测试任务
    - viewer (1) : 只读成员，仅可查看项目数据和测试报告

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from typing import Dict, List

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, String,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.utils.db_time import utcnow


# 角色层级映射，数值越大权限越高，用于角色比较与访问校验
ROLE_LEVEL: Dict[str, int] = {
    "viewer": 1,
    "member": 2,
    "admin": 3,
    "owner": 4,
}

# 所有合法角色列表
VALID_ROLES: List[str] = list(ROLE_LEVEL.keys())


class ProjectMember(Base):
    """项目成员模型 - 用户与项目的多对多关联，带角色层级。

    每条记录描述「某用户在某项目中拥有某种角色」，ProjectAccessService
    通过本表校验用户对项目的访问权限，替代原有 Project.user_id 单一属主校验。

    表关系：
        - 多对一 → Project（项目，级联删除）
        - 多对一 → User（用户，级联删除）

    使用场景：
        - 项目权限校验：ProjectAccessService.check_project_access
        - 成员管理：添加/移除/更新成员角色
        - 项目成员列表查询

    约束：
        - (project_id, user_id) 唯一约束，防止同一用户在同一项目中有多条成员记录
    """
    __tablename__ = "project_members"
    __table_args__ = (
        # 唯一约束：同一用户在同一项目中只能有一条成员记录
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        # 复合索引：按项目查询成员列表（含角色排序）
        Index("ix_project_member_role", "project_id", "role"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="成员记录主键ID")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    role = Column(String(20), nullable=False, default="member", comment="成员角色: owner/admin/member/viewer")
    created_at = Column(DateTime, nullable=False, default=utcnow, comment="创建时间（UTC）")
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, comment="更新时间（UTC）")

    # 关联关系
    project = relationship("Project", backref="members")
    user = relationship("User", backref="project_memberships")

    def __repr__(self) -> str:
        """返回成员记录的字符串表示，便于调试与日志输出。"""
        return (
            f"<ProjectMember(id={self.id}, project_id={self.project_id}, "
            f"user_id={self.user_id}, role={self.role})>"
        )

    def to_dict(self) -> dict:
        """转换为字典格式，供 API 响应与日志输出使用。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def is_valid_role(role: str) -> bool:
        """校验角色是否合法。"""
        return role in ROLE_LEVEL

    @staticmethod
    def role_level(role: str) -> int:
        """获取角色层级数值，非法角色返回 0。"""
        return ROLE_LEVEL.get(role, 0)