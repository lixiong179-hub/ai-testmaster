"""
用户与权限模型模块

本模块定义了基于 RBAC（基于角色的访问控制）的用户-角色-权限体系，
是整个系统的认证与授权基础。

核心类概览：
    - User       : 用户模型，存储账号信息与安全策略字段
    - Role       : 角色模型，以 JSON 列表存储权限 code，简化权限校验
    - Permission : 权限模型，支持树形结构（自引用父级权限）
    - UserRole   : 用户-角色关联映射类（兼容测试代码的显式导入）

表关系：
    User ←→ Role（多对多，通过 user_role 关联表）
    Role ←→ Permission（多对多，通过 role_permission 关联表）
    Permission → Permission（自引用，树形结构）
    User → Project（一对多，用户拥有多个项目）
    User → TestTask（一对多，用户执行多个测试任务）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Table, JSON
from sqlalchemy.orm import relationship
from app.utils.db_time import utcnow
from app.db.database import Base

# 用户-角色多对多关联表
# 级联删除：删除用户或角色时，自动清除关联记录
user_role = Table(
    'user_role',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),  # 用户ID，级联删除
    Column('role_id', Integer, ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True)    # 角色ID，级联删除
)

# 角色-权限多对多关联表
# 级联删除：删除角色或权限时，自动清除关联记录
role_permission = Table(
    'role_permission',
    Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),        # 角色ID，级联删除
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete="CASCADE"), primary_key=True)  # 权限ID，级联删除
)


class UserRole(Base):
    """
    用户-角色关联映射类

    提供对 user_role 关联表的 ORM 映射，便于在需要时直接对关联表进行
    查询或操作（如批量删除、统计等）。

    注意：业务层的多对多关系仍通过 User.roles / Role.users 的
    secondary=user_role 参数实现，本类仅作为补充。
    """

    __table__ = user_role


class User(Base):
    """
    用户模型

    存储系统用户的核心信息，包括认证凭据、安全策略字段和关联关系。
    支持本地账号认证和外部系统（LDAP/SSO）集成。

    表关系：
        - 多对多 → Role（通过 user_role 关联表）
        - 一对多 → Project（用户拥有的项目）
        - 一对多 → TestTask（用户执行的测试任务）

    使用场景：
        - 用户注册、登录、权限校验
        - 账户安全策略（登录失败锁定、登录计数）
        - 外部系统集成（LDAP/SSO 单点登录）
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)                          # 用户主键ID
    username = Column(String(50), nullable=False, unique=True, index=True)      # 用户名，唯一且索引，用于登录
    email = Column(String(100), nullable=False, unique=True, index=True)        # 邮箱，唯一且索引，用于通知和找回密码
    phone = Column(String(20), nullable=True, index=True)                       # 手机号，可选，索引用于快速查找
    password_hash = Column(String(255), nullable=False)                         # 密码哈希值，禁止存储明文密码
    is_active = Column(Boolean, default=True)                                   # 账户是否激活，默认True
    is_superuser = Column(Boolean, default=False)                               # 是否超级管理员，默认False
    create_time = Column(DateTime, default=utcnow)                              # 创建时间，UTC时区
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow)             # 更新时间，记录变更时自动更新

    # 安全增强字段
    last_login_time = Column(DateTime, nullable=True, comment="最后登录时间")     # 用于安全审计和会话管理
    login_count = Column(Integer, nullable=True, default=0, comment="登录次数")   # 统计用户活跃度
    external_id = Column(String(100), nullable=True, comment="外部系统ID（如LDAP/SSO）")  # 外部认证系统的用户标识
    external_system = Column(String(50), nullable=True, comment="外部系统名称")   # 如 ldap、sso_cas 等
    failed_login_attempts = Column(Integer, nullable=False, default=0, comment="失败登录次数")  # 连续失败计数，用于锁定策略
    locked_until = Column(DateTime, nullable=True, comment="账户锁定截止时间")    # 超过失败阈值后锁定至该时间

    # 关联关系
    roles = relationship("Role", secondary=user_role, back_populates="users")    # 用户拥有的角色列表（多对多）
    # 关联项目（用户可以拥有多个项目）
    projects = relationship("Project", back_populates="owner", foreign_keys="Project.user_id")  # 用户创建的项目
    # 关联测试任务（用户可以执行多个测试任务）
    test_tasks = relationship("TestTask", back_populates="executor")             # 用户执行的测试任务


class Role(Base):
    """
    角色模型

    定义系统角色，采用简化设计：权限以 JSON 列表形式存储在 permissions 字段中，
    列表元素为 Permission.code 字符串。此设计兼容现有服务层与单测期望，
    避免了 role_permission 关联表的复杂查询。

    表关系：
        - 多对多 → User（通过 user_role 关联表）
        - permissions 字段存储权限 code 列表，关联 Permission.code

    使用场景：
        - RBAC 权限校验：判断用户是否拥有某权限时，遍历用户角色列表的 permissions
        - 角色管理：创建、编辑、删除角色及分配权限
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)                          # 角色主键ID
    name = Column(String(50), nullable=False, unique=True)                      # 角色名称，唯一，如 admin/tester/viewer
    desc = Column(Text, nullable=True)                                          # 角色描述，说明角色职责
    # 简化：以JSON列表存储权限code（兼容现有服务层与单测期望）
    # 格式示例：["project:create", "test_case:read", "test_case:update"]
    permissions = Column(JSON, nullable=True)                                   # 权限code列表，JSON格式
    create_time = Column(DateTime, default=utcnow)                              # 创建时间
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow)             # 更新时间

    # 关联关系
    users = relationship("User", secondary=user_role, back_populates="roles")   # 拥有该角色的用户列表（多对多）


class Permission(Base):
    """
    权限模型

    定义系统细粒度权限，支持树形结构（通过 parent_id 自引用）。
    每个权限由 code 唯一标识，关联资源类型和操作动作。

    表关系：
        - 自引用 → Permission（parent_id，树形结构）
        - 被 Role.permissions 字段引用（JSON 列表中的 code 值）

    使用场景：
        - 权限定义与树形展示
        - 角色分配权限时选择权限节点
        - 接口鉴权时校验当前用户是否拥有对应 code 的权限

    权限层级示例：
        project（项目管理）
        ├── project:create（创建项目）
        ├── project:read（查看项目）
        ├── project:update（更新项目）
        └── project:delete（删除项目）
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)                          # 权限主键ID
    name = Column(String(50), nullable=False, unique=True)                      # 权限显示名称，如"创建项目"
    code = Column(String(50), nullable=False, unique=True)                      # 权限唯一编码，如"project:create"
    type = Column(String(20), nullable=False, default="api")                    # 权限类型：api=接口权限，menu=菜单权限，data=数据权限
    resource_type = Column(String(50), nullable=True, comment="资源类型（如project/test_case/user）")  # 权限所属资源类型
    action = Column(String(20), nullable=True, comment="操作动作（如create/read/update/delete）")       # CRUD操作类型
    parent_id = Column(Integer, ForeignKey("permissions.id"), nullable=True)    # 父级权限ID，构成树形结构
    description = Column(Text, nullable=True)                                   # 权限详细说明
    create_time = Column(DateTime, default=utcnow)                              # 创建时间
    update_time = Column(DateTime, onupdate=utcnow, default=utcnow)             # 更新时间

    # 关联关系（可选，自引用）
    parent = relationship("Permission", remote_side=[id], backref="children")   # 父级权限，remote_side指定自引用远端
