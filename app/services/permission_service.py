"""权限服务 - 提供权限CRUD、用户角色分配与RBAC访问控制。

本模块实现平台权限体系的核心服务，包括权限的创建/查询/更新/删除、
用户与角色的关联管理、以及基于角色的访问控制（RBAC）校验。

核心类:
    - PermissionService: 权限CRUD服务
    - UserRoleService: 用户-角色关联服务
    - RBACService: 基于角色的访问控制服务

依赖关系:
    - app.models.user: Permission/Role/user_role ORM模型
    - app.schemas.user: 权限相关Schema
    - app.core.exception: BaseAPIException统一异常
    - app.services.user_role_service: UserService/RoleService

RBAC模型:
    用户 -> 角色 -> 权限
    - 用户通过user_role关联表绑定多个角色
    - 角色通过permissions字段（JSON列表）存储权限编码
    - RBACService.check_permission通过用户角色链校验权限

安全设计:
    - 权限编码全局唯一，防止重复创建
    - 角色分配幂等性校验，防止重复分配
    - 权限校验采用白名单模式，默认无权限
"""
from typing import Optional, List, Union
from sqlalchemy import select, delete, and_
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import Permission, Role, user_role
from app.schemas.user import PermissionCreate, PermissionUpdate
from app.core.exception import BaseAPIException
from app.services.user_service.user_service import UserService
from app.services.role_service.role_service import RoleService
from app.services.user_role_service_async_mixin import UserRoleServiceAsyncMixin
from app.services.permission_service_async_mixin import PermissionServiceAsyncMixin


class PermissionService(PermissionServiceAsyncMixin):
    """权限CRUD服务 - 管理权限的全生命周期。

    职责:
        - 创建权限（含编码唯一性校验）
        - 查询权限
        - 更新权限（部分更新）
        - 删除权限

    使用场景:
        - 权限管理页面调用CRUD方法
        - 系统初始化时创建基础权限

    hybrid 模式：sync 调用方使用静态方法（db 作为首参传入），
    async 端点通过 PermissionService(db) 实例化后调用 *_async 方法。
    """

    def __init__(self, db: Optional[Union[Session, AsyncSession]] = None) -> None:
        """初始化权限服务。

        Args:
            db: 数据库会话，async 端点传 AsyncSession；sync 调用方
                无需实例化，直接使用静态方法。
        """
        self.db = db

    @staticmethod
    def create_permission(db: Session, permission_in: PermissionCreate | dict) -> Permission:
        """创建新权限，含编码唯一性校验。

        Args:
            db: 数据库会话。
            permission_in: 权限创建参数，支持PermissionCreate Schema或dict。

        Returns:
            创建成功的Permission ORM实例。

        Raises:
            BaseAPIException: 权限编码已存在(400)。
        """
        # 参数适配
        if isinstance(permission_in, dict):
            permission_in = PermissionCreate(**permission_in)

        # 校验权限编码唯一性
        existing_perm = db.execute(
            select(Permission).where(Permission.code == permission_in.code)
        ).scalars().first()
        if existing_perm:
            raise BaseAPIException("权限编码已存在", code=400)

        db_perm = Permission(
            name=permission_in.name,
            code=permission_in.code,
            type=permission_in.type,
            parent_id=permission_in.parent_id
        )
        db.add(db_perm)
        db.commit()
        db.refresh(db_perm)
        return db_perm

    @staticmethod
    def get_permission_by_id(db: Session, perm_id: int) -> Optional[Permission]:
        """根据权限ID查询权限。

        Args:
            db: 数据库会话。
            perm_id: 权限唯一标识。

        Returns:
            Permission实例，不存在时返回None。
        """
        return db.execute(select(Permission).where(Permission.id == perm_id)).scalars().first()

    @staticmethod
    def update_permission(db: Session, perm_id: int, perm_in: PermissionUpdate | dict) -> Permission:
        """更新权限信息，仅修改传入的字段（部分更新）。

        Args:
            db: 数据库会话。
            perm_id: 待更新的权限ID。
            perm_in: 更新参数，支持PermissionUpdate Schema或dict。

        Returns:
            更新后的Permission实例。

        Raises:
            BaseAPIException: 权限不存在(404)。
        """
        # 参数适配
        if isinstance(perm_in, dict):
            perm_in = PermissionUpdate(**perm_in)

        perm = PermissionService.get_permission_by_id(db, perm_id)
        if not perm:
            raise BaseAPIException("权限不存在", code=404)

        # 部分更新，未传入字段保持原值
        update_data = perm_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(perm, field, value)
        db.commit()
        db.refresh(perm)
        return perm

    @staticmethod
    def delete_permission(db: Session, perm_id: int) -> bool:
        """删除权限。

        Args:
            db: 数据库会话。
            perm_id: 待删除的权限ID。

        Returns:
            删除成功返回True。

        Raises:
            BaseAPIException: 权限不存在(404)。
        """
        perm = PermissionService.get_permission_by_id(db, perm_id)
        if not perm:
            raise BaseAPIException("权限不存在", code=404)
        db.delete(perm)
        db.commit()
        return True

    @staticmethod
    def get_permissions(db: Session, skip: int = 0, limit: int = 100) -> List[Permission]:
        """分页查询权限列表。

        Args:
            db: 数据库会话。
            skip: 跳过的记录数，用于分页偏移。
            limit: 每页最大记录数，默认100。

        Returns:
            Permission实例列表。
        """
        return db.execute(select(Permission).offset(skip).limit(limit)).scalars().all()


class UserRoleService(UserRoleServiceAsyncMixin):
    """用户-角色关联服务 - 管理用户与角色的绑定关系。

    职责:
        - 为用户分配角色（含幂等性校验）
        - 移除用户的角色
        - 查询用户的角色列表

    使用场景:
        - 角色分配页面调用assign_role
        - 角色管理页面调用remove_role
        - 权限校验前通过get_user_roles获取用户角色

    hybrid 模式：sync 调用方使用静态方法（db 作为首参传入），
    async 端点通过 UserRoleService(db) 实例化后调用 *_async 方法。
    """

    def __init__(self, db: Optional[Union[Session, AsyncSession]] = None) -> None:
        """初始化用户-角色关联服务。

        Args:
            db: 数据库会话，async 端点传 AsyncSession；sync 调用方
                无需实例化，直接使用静态方法。
        """
        self.db = db

    @staticmethod
    def assign_role(db: Session, user_id: int, role_id: int) -> bool:
        """为用户分配角色，含幂等性校验。

        Args:
            db: 数据库会话。
            user_id: 用户ID。
            role_id: 角色ID。

        Returns:
            分配成功返回True。

        Raises:
            BaseAPIException: 用户不存在(404)、角色不存在(404)、角色已分配(400)。
        """
        # 校验用户和角色是否存在
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise BaseAPIException("用户不存在", code=404)
        role = RoleService.get_role_by_id(db, role_id)
        if not role:
            raise BaseAPIException("角色不存在", code=404)

        # 幂等性校验，防止重复分配
        existing = db.execute(
            select(user_role).where(
                and_(user_role.c.user_id == user_id, user_role.c.role_id == role_id)
            )
        )
        if existing.scalars().first():
            raise BaseAPIException("角色已分配", code=400)

        db.execute(user_role.insert().values(user_id=user_id, role_id=role_id))
        db.commit()
        return True

    @staticmethod
    def remove_role(db: Session, user_id: int, role_id: int) -> bool:
        """移除用户的角色分配。

        Args:
            db: 数据库会话。
            user_id: 用户ID。
            role_id: 角色ID。

        Returns:
            移除成功返回True。

        Raises:
            BaseAPIException: 角色分配不存在(404)。
        """
        result = db.execute(
            delete(user_role).where(
                and_(user_role.c.user_id == user_id, user_role.c.role_id == role_id)
            )
        )
        db.commit()
        if result.rowcount == 0:
            raise BaseAPIException("角色分配不存在", code=404)
        return True

    @staticmethod
    def get_user_roles(db: Session, user_id: int) -> List[Role]:
        """查询用户的所有角色。

        Args:
            db: 数据库会话。
            user_id: 用户ID。

        Returns:
            Role实例列表。
        """
        return db.execute(
            select(Role).join(user_role).where(user_role.c.user_id == user_id)
        ).scalars().all()


class RBACService:
    """基于角色的访问控制服务 - 校验用户是否拥有指定权限。

    RBAC模型:
        用户 -> 角色 -> 权限编码列表

        校验流程:
        1. 获取用户的所有角色
        2. 遍历角色的permissions字段（JSON列表）
        3. 检查目标权限编码是否在任一角色的权限列表中

    使用场景:
        - API接口权限校验
        - 前端功能按钮可见性控制
        - 数据访问权限过滤

    安全设计:
        采用白名单模式，默认无权限。
        只有明确匹配到权限编码才返回True。
    """

    @staticmethod
    def check_permission(db: Session, user_id: int, permission_code: str) -> bool:
        """校验用户是否拥有指定权限编码的权限。

        Args:
            db: 数据库会话。
            user_id: 用户ID。
            permission_code: 权限编码，如"user:create"、"report:export"。

        Returns:
            有权限返回True，无权限返回False。
        """
        roles = UserRoleService.get_user_roles(db, user_id)
        for role in roles:
            if role.permissions and permission_code in role.permissions:
                return True
        return False
