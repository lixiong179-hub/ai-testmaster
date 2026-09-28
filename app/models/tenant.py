"""Phase 3 Task 9: 租户模型。

核心概念：
    - Tenant : 租户实体，一个租户对应一个企业/组织
    - User   : 用户通过 tenant_id 关联到租户
    - Project: 项目通过 tenant_id 关联到租户，实现行级隔离

行级安全设计：
    - 所有核心业务表添加 tenant_id 字段
    - 查询时通过 TenantQueryFilter 自动追加 tenant_id 过滤
    - JWT 令牌携带 tenant_id claim，由 TenantContext 提取

表关系：
    Tenant ←→ User（一对多）
    Tenant ←→ Project（一对多）
    Tenant ←→ 其他业务表（一对多，通过 tenant_id）
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base


class Tenant(Base):
    """租户模型 — 企业/组织级别的数据隔离单元。

    使用场景：
        - SaaS 多租户隔离：不同企业数据互不可见
        - 行级安全：所有业务表通过 tenant_id 隔离
        - 资源配额：按租户限制项目数、用例数等

    属性：
        name        : 租户名称（企业/组织名）
        slug        : URL 友好的唯一标识（用于子域名等）
        status      : 状态（active/suspended/deleted）
        max_projects: 最大项目数配额
        max_users   : 最大用户数配额
    """

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="租户名称（企业/组织名）")
    slug = Column(String(50), nullable=False, unique=True, index=True, comment="URL 友好唯一标识")
    status = Column(String(20), nullable=False, default="active", comment="状态: active/suspended/deleted")
    max_projects = Column(Integer, nullable=False, default=100, comment="最大项目数配额")
    max_users = Column(Integer, nullable=False, default=50, comment="最大用户数配额")
    is_active = Column(Boolean, default=True, comment="是否激活")
    create_time = Column(DateTime, default=utcnow, comment="创建时间")
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow, comment="更新时间")

    # 关联关系
    users = relationship("User", back_populates="tenant", foreign_keys="User.tenant_id")
    projects = relationship("Project", back_populates="tenant", foreign_keys="Project.tenant_id")


__all__ = ["Tenant"]
