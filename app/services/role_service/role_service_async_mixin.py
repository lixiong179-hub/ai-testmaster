"""角色服务异步 Mixin。

从 sync 版本（RoleService 静态方法）镜像出 async 实例方法，供 async 端点
直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync 静态方法共存（hybrid 模式），sync 调用方继续用静态方法；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - 方法名加 _async 后缀避免与 sync 静态方法冲突；
    - self.db 在运行时为 AsyncSession 实例。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = RoleService(db)  # db 为 AsyncSession
        role = await service.create_role_async(role_in)
"""
from typing import Optional, List

from sqlalchemy import select, delete

from app.models.user import Role, user_role
from app.schemas.user import RoleCreate, RoleUpdate
from app.core.exception import BaseAPIException


class RoleServiceAsyncMixin:
    """角色服务异步操作 Mixin，供 RoleService 继承。

    要求 self.db 为 AsyncSession 实例。
    """

    async def create_role_async(self, role_in: RoleCreate | dict) -> Role:
        """创建新角色（异步版本），含名称唯一性校验。

        Raises:
            BaseAPIException: 角色名称已存在(400)。
        """
        if isinstance(role_in, dict):
            role_in = RoleCreate(**role_in)

        result = await self.db.execute(
            select(Role).where(Role.name == role_in.name)
        )
        if result.scalars().first():
            raise BaseAPIException("角色名称已存在", code=400)

        db_role = Role(
            name=role_in.name,
            desc=role_in.desc,
            permissions=role_in.permissions,
        )
        self.db.add(db_role)
        await self.db.commit()
        await self.db.refresh(db_role)
        return db_role

    async def get_role_by_id_async(self, role_id: int) -> Optional[Role]:
        """根据角色ID查询角色（异步版本）。"""
        result = await self.db.execute(
            select(Role).where(Role.id == role_id)
        )
        return result.scalars().first()

    async def update_role_async(
        self, role_id: int, role_in: RoleUpdate | dict
    ) -> Role:
        """更新角色信息（异步版本），仅修改传入字段。

        Raises:
            BaseAPIException: 角色不存在(404)。
        """
        if isinstance(role_in, dict):
            role_in = RoleUpdate(**role_in)

        role = await self.get_role_by_id_async(role_id)
        if not role:
            raise BaseAPIException("角色不存在", code=404)

        update_data = role_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(role, field, value)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def delete_role_async(self, role_id: int) -> bool:
        """删除角色及其用户关联关系（异步版本）。

        先清理 user_role 关联表，再删除角色本体，避免外键约束冲突。

        Raises:
            BaseAPIException: 角色不存在(404)。
        """
        role = await self.get_role_by_id_async(role_id)
        if not role:
            raise BaseAPIException("角色不存在", code=404)

        await self.db.execute(
            delete(user_role).where(user_role.c.role_id == role_id)
        )
        await self.db.delete(role)
        await self.db.commit()
        return True

    async def get_roles_async(
        self, skip: int = 0, limit: int = 100
    ) -> List[Role]:
        """分页查询角色列表（异步版本）。"""
        result = await self.db.execute(
            select(Role).offset(skip).limit(limit)
        )
        return result.scalars().all()
