"""权限服务异步 Mixin。

从 sync 版本（PermissionService 静态方法）镜像出 async 实例方法，供 async 端点
直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync 静态方法共存（hybrid 模式），sync 调用方继续用静态方法；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - 方法名加 _async 后缀避免与 sync 静态方法冲突；
    - self.db 在运行时为 AsyncSession 实例。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = PermissionService(db)  # db 为 AsyncSession
        perm = await service.create_permission_async(perm_in)
"""
from typing import Optional, List

from sqlalchemy import select

from app.models.user import Permission
from app.schemas.user import PermissionCreate, PermissionUpdate
from app.core.exception import BaseAPIException


class PermissionServiceAsyncMixin:
    """权限服务异步操作 Mixin，供 PermissionService 继承。

    要求 self.db 为 AsyncSession 实例。
    """

    async def create_permission_async(
        self, permission_in: PermissionCreate | dict
    ) -> Permission:
        """创建新权限（异步版本），含编码唯一性校验。

        Raises:
            BaseAPIException: 权限编码已存在(400)。
        """
        if isinstance(permission_in, dict):
            permission_in = PermissionCreate(**permission_in)

        result = await self.db.execute(
            select(Permission).where(Permission.code == permission_in.code)
        )
        if result.scalars().first():
            raise BaseAPIException("权限编码已存在", code=400)

        db_perm = Permission(
            name=permission_in.name,
            code=permission_in.code,
            type=permission_in.type,
            parent_id=permission_in.parent_id,
        )
        self.db.add(db_perm)
        await self.db.commit()
        await self.db.refresh(db_perm)
        return db_perm

    async def get_permission_by_id_async(self, perm_id: int) -> Optional[Permission]:
        """根据权限ID查询权限（异步版本）。"""
        result = await self.db.execute(
            select(Permission).where(Permission.id == perm_id)
        )
        return result.scalars().first()

    async def update_permission_async(
        self, perm_id: int, perm_in: PermissionUpdate | dict
    ) -> Permission:
        """更新权限信息（异步版本），仅修改传入字段。

        Raises:
            BaseAPIException: 权限不存在(404)。
        """
        if isinstance(perm_in, dict):
            perm_in = PermissionUpdate(**perm_in)

        perm = await self.get_permission_by_id_async(perm_id)
        if not perm:
            raise BaseAPIException("权限不存在", code=404)

        update_data = perm_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(perm, field, value)
        await self.db.commit()
        await self.db.refresh(perm)
        return perm

    async def delete_permission_async(self, perm_id: int) -> bool:
        """删除权限（异步版本）。

        Raises:
            BaseAPIException: 权限不存在(404)。
        """
        perm = await self.get_permission_by_id_async(perm_id)
        if not perm:
            raise BaseAPIException("权限不存在", code=404)
        await self.db.delete(perm)
        await self.db.commit()
        return True

    async def get_permissions_async(
        self, skip: int = 0, limit: int = 100
    ) -> List[Permission]:
        """分页查询权限列表（异步版本）。"""
        result = await self.db.execute(
            select(Permission).offset(skip).limit(limit)
        )
        return result.scalars().all()
