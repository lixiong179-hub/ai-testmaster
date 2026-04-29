"""
资源权限模型模块

本模块定义了资源权限（ResourcePermission）模型，实现细粒度的资源级权限控制，
支持对特定资源（项目、用例等）分配特定角色和权限。

核心类概览：
    - ResourcePermission : 资源权限模型，联合主键设计

表关系：
    Role → ResourcePermission（一对多，级联删除）
    Permission → ResourcePermission（一对多，级联删除）

依赖关系：
    - app.db.database.Base : SQLAlchemy 声明性基类

设计说明：
    采用联合主键（resource_id + resource_type + role_id + permission_id），
    确保同一资源上同一角色的同一权限不会重复分配。
"""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class ResourcePermission(Base):
    """
    资源权限模型 - 联合主键设计

    实现细粒度的资源级权限控制，支持对特定资源实例分配特定角色和权限。
    与全局权限（Role.permissions）不同，资源权限限定在特定资源范围内。

    联合主键：
        - resource_id   : 资源实例ID
        - resource_type : 资源类型（project/test_case/test_task）
        - role_id       : 角色ID
        - permission_id : 权限ID

    表关系：
        - 多对一 → Role（角色，级联删除）
        - 多对一 → Permission（权限，级联删除）

    使用场景：
        - 项目级别的角色权限分配
        - 特定用例的编辑权限控制
        - 细粒度的资源访问控制
    """
    __tablename__ = "resource_permission"

    resource_id = Column(Integer, nullable=False, primary_key=True, comment="资源ID")                  # 资源实例ID
    resource_type = Column(String(50), nullable=False, primary_key=True, comment="资源类型: project/test_case/test_task")  # project=项目，test_case=用例，test_task=任务
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, primary_key=True, comment="角色ID")  # 角色ID，级联删除
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, primary_key=True, comment="权限ID")  # 权限ID，级联删除

    # 关联关系
    role = relationship("Role")                                                                       # 关联角色
    permission = relationship("Permission")                                                           # 关联权限

    def __repr__(self) -> str:
        """返回资源权限的字符串表示，便于调试和日志输出。"""
        return f"<ResourcePermission(resource={self.resource_type}:{self.resource_id}, role={self.role_id})>"
