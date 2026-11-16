"""权限服务异步桥接 Mixin（R2-1 阶段三：会话层单范式收敛）。

单范式后 ``self.db`` 为**同步** ``Session``（端点 ``Depends(get_db)``），
本 Mixin 只保留 ``*_async`` 方法名做兼容，内部统一走 ``asyncio.to_thread``
调用同名 sync 静态方法（``PermissionService.create_permission`` 等）。

约定：禁止在本文件出现 ``await self.db.xxx(...)``／``select()`` 等异步 DB 代码。
"""

import asyncio

from app.models.user import Permission
from app.schemas.user import PermissionCreate, PermissionUpdate


class PermissionServiceAsyncMixin:
    """``*_async`` 方法 = sync 静态方法 + ``asyncio.to_thread``（``self.db`` 为 Session）。"""

    async def create_permission_async(
        self, permission_in: PermissionCreate | dict
    ) -> Permission:
        """创建新权限（异步桥接），含编码唯一性校验。"""
        return await asyncio.to_thread(self.create_permission, self.db, permission_in)

    async def get_permission_by_id_async(self, perm_id: int) -> Permission | None:
        """根据权限ID查询权限（异步桥接）。"""
        return await asyncio.to_thread(self.get_permission_by_id, self.db, perm_id)

    async def update_permission_async(
        self, perm_id: int, perm_in: PermissionUpdate | dict
    ) -> Permission:
        """更新权限信息（异步桥接），仅修改传入字段。"""
        return await asyncio.to_thread(self.update_permission, self.db, perm_id, perm_in)

    async def delete_permission_async(self, perm_id: int) -> bool:
        """删除权限（异步桥接）。"""
        return await asyncio.to_thread(self.delete_permission, self.db, perm_id)

    async def get_permissions_async(
        self, skip: int = 0, limit: int = 100
    ) -> list[Permission]:
        """分页查询权限列表（异步桥接）。"""
        return await asyncio.to_thread(self.get_permissions, self.db, skip, limit)
