"""
用户组权限模型模块

本模块定义了用户组（Group）模型及其与用户、角色的多对多关联关系，
实现更灵活的权限管理和团队协作。用户组允许按团队批量分配角色和权限。

核心类概览：
    - Group : 用户组模型，管理用户组信息和关联关系

表关系：
    User ←→ Group（多对多，通过 user_group 关联表）
    Group ←→ Role（多对多，通过 group_role 关联表）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类

注意：
    本模块通过动态扩展 User 和 Role 模型添加 groups 关联关系。
"""
from datetime import datetime
from app.utils.db_time import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


# 用户-用户组多对多关联表
# 级联删除：删除用户或用户组时，自动清除关联记录
user_group = Table(
    'user_group',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),   # 用户ID，级联删除
    Column('group_id', Integer, ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)  # 用户组ID，级联删除
)

# 用户组-角色多对多关联表
# 级联删除：删除用户组或角色时，自动清除关联记录
group_role = Table(
    'group_role',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True),   # 用户组ID，级联删除
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)      # 角色ID，级联删除
)


class Group(Base):
    """
    用户组模型

    管理用户组信息，支持按团队批量分配角色和权限。
    用户组是用户和角色之间的中间层，允许按组织结构管理权限。

    表关系：
        - 多对多 → User（通过 user_group 关联表）
        - 多对多 → Role（通过 group_role 关联表）

    使用场景：
        - 按团队/部门组织用户
        - 批量分配角色给用户组
        - 团队级别的权限管理
    """
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)                            # 用户组主键ID
    name = Column(String(50), nullable=False, unique=True, comment="组名")                             # 用户组名称，唯一
    desc = Column(Text, nullable=True, comment="组描述")                                               # 用户组描述
    create_time = Column(DateTime, default=utcnow, comment="创建时间")                                 # 创建时间，UTC时区
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow, comment="更新时间")                # 更新时间

    # 关联关系
    users = relationship("User", secondary=user_group, back_populates="groups")                       # 组内用户列表（多对多）
    roles = relationship("Role", secondary=group_role, back_populates="groups")                       # 组拥有的角色（多对多）

    def __repr__(self) -> str:
        """返回用户组的字符串表示，便于调试和日志输出。"""
        return f"<Group(id={self.id}, name='{self.name}')>"


# 扩展User模型添加groups关系
from app.models.user import User
User.groups = relationship("Group", secondary=user_group, back_populates="users")                     # 动态扩展User模型，添加用户组关联

# 扩展Role模型添加groups关系
from app.models.user import Role
Role.groups = relationship("Group", secondary=group_role, back_populates="roles")                     # 动态扩展Role模型，添加用户组关联
