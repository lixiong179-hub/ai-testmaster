"""角色服务异步桥接 Mixin（R2-1 阶段三：会话层单范式收敛）。

单范式后 ``self.db`` 为**同步** ``Session``（端点 ``Depends(get_db)``），
本 Mixin 只保留 ``*_async`` 方法名做兼容，内部统一走 ``asyncio.to_thread``
调用同名 sync 静态方法（``RoleService.create_role`` 等）。

约定：禁止在本文件出现 ``await self.db.xxx(...)``／``select()`` 等异步 DB 代码。
"""

import asyncio

from app.models.user import Role
from app.schemas.user import RoleCreate, RoleUpdate


class RoleServiceAsyncMixin:
    """``*_async`` 方法 = sync 静态方法 + ``asyncio.to_thread``（``self.db`` 为 Session）。"""

    async def create_role_async(self, role_in: RoleCreate | dict) -> Role:
        """创建新角色（异步桥接），含名称唯一性校验。"""
        return await asyncio.to_thread(self.create_role, self.db, role_in)

    async def get_role_by_id_async(self, role_id: int) -> Role | None:
        """根据角色ID查询角色（异步桥接）。"""
        return await asyncio.to_thread(self.get_role_by_id, self.db, role_id)

    async def update_role_async(self, role_id: int, role_in: RoleUpdate | dict) -> Role:
        """更新角色信息（异步桥接），仅修改传入字段。"""
        return await asyncio.to_thread(self.update_role, self.db, role_id, role_in)

    async def delete_role_async(self, role_id: int) -> bool:
        """删除角色及其用户关联（异步桥接）。"""
        return await asyncio.to_thread(self.delete_role, self.db, role_id)

    async def get_roles_async(self, skip: int = 0, limit: int = 100) -> list[Role]:
        """分页查询角色列表（异步桥接）。"""
        return await asyncio.to_thread(self.get_roles, self.db, skip, limit)
