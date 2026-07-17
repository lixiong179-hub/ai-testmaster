
"""角色服务 - 处理角色CRUD与权限分配。

职责:
    - 角色创建（含名称唯一性校验）
    - 角色查询与更新
    - 角色删除（级联清理用户关联）

使用场景:
    - 角色管理页面调用CRUD方法
    - 权限配置时创建/更新角色及其权限列表

设计意图:
    与UserService保持一致的静态方法设计，数据库会话
    由调用方管理，确保事务边界清晰。
"""
from typing import Optional, List, Union
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import Role, user_role
from app.schemas.user import RoleCreate, RoleUpdate
from app.core.exception import BaseAPIException
from app.services.role_service.role_service_async_mixin import RoleServiceAsyncMixin


class RoleService(RoleServiceAsyncMixin):
    """角色服务 - 处理角色CRUD与权限分配。

    hybrid 模式：sync 调用方使用静态方法（db 作为首参传入），
    async 端点通过 RoleService(db) 实例化后调用 *_async 方法。
    """

    def __init__(self, db: Optional[Union[Session, AsyncSession]] = None) -> None:
        """初始化角色服务。

        Args:
            db: 数据库会话，async 端点传 AsyncSession；sync 调用方
                无需实例化，直接使用静态方法。
        """
        self.db = db

    @staticmethod
    def create_role(db: Session, role_in: RoleCreate | dict) -> Role:
        """创建新角色，含名称唯一性校验。

        Args:
            db: 数据库会话。
            role_in: 角色创建参数，支持RoleCreate Schema或dict。

        Returns:
            创建成功的Role ORM实例。

        Raises:
            BaseAPIException: 角色名称已存在(400)。
        """
        # 参数适配
        if isinstance(role_in, dict):
            role_in = RoleCreate(**role_in)

        # 校验角色名称唯一性
        existing_role = db.execute(select(Role).where(Role.name == role_in.name)).scalars().first()
        if existing_role:
            raise BaseAPIException("角色名称已存在", code=400)

        db_role = Role(name=role_in.name, desc=role_in.desc, permissions=role_in.permissions)
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def get_role_by_id(db: Session, role_id: int) -> Optional[Role]:
        """根据角色ID查询角色。

        Args:
            db: 数据库会话。
            role_id: 角色唯一标识。

        Returns:
            Role实例，不存在时返回None。
        """
        return db.execute(select(Role).where(Role.id == role_id)).scalars().first()

    @staticmethod
    def update_role(db: Session, role_id: int, role_in: RoleUpdate | dict) -> Role:
        """更新角色信息，仅修改传入的字段（部分更新）。

        Args:
            db: 数据库会话。
            role_id: 待更新的角色ID。
            role_in: 更新参数，支持RoleUpdate Schema或dict。

        Returns:
            更新后的Role实例。

        Raises:
            BaseAPIException: 角色不存在(404)。
        """
        # 参数适配
        if isinstance(role_in, dict):
            role_in = RoleUpdate(**role_in)

        role = RoleService.get_role_by_id(db, role_id)
        if not role:
            raise BaseAPIException("角色不存在", code=404)

        # 部分更新，未传入字段保持原值
        update_data = role_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(role, field, value)
        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete_role(db: Session, role_id: int) -> bool:
        """删除角色及其用户关联关系。

        先清理user_role关联表中的记录，再删除角色本体，
        避免外键约束冲突。

        Args:
            db: 数据库会话。
            role_id: 待删除的角色ID。

        Returns:
            删除成功返回True。

        Raises:
            BaseAPIException: 角色不存在(404)。
        """
        role = RoleService.get_role_by_id(db, role_id)
        if not role:
            raise BaseAPIException("角色不存在", code=404)

        # 先清理用户-角色关联，再删除角色，保证数据一致性
        db.execute(delete(user_role).where(user_role.c.role_id == role_id))
        db.delete(role)
        db.commit()
        return True

    @staticmethod
    def get_roles(db: Session, skip: int = 0, limit: int = 100) -> List[Role]:
        """分页查询角色列表。

        Args:
            db: 数据库会话。
            skip: 跳过的记录数，用于分页偏移。
            limit: 每页最大记录数，默认100。

        Returns:
            Role实例列表。
        """
        return db.execute(select(Role).offset(skip).limit(limit)).scalars().all()
