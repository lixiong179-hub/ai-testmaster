"""用户-角色关联服务异步桥接 Mixin（R2-1 阶段三：会话层单范式收敛）。

单范式后 ``self.db`` 为**同步** ``Session``（端点 ``Depends(get_db)``），
本 Mixin 只保留 ``*_async`` 方法名做兼容，内部统一走 ``asyncio.to_thread``
调用同名 sync 静态方法（``UserRoleService.assign_role`` 等）。

约定：禁止在本文件出现 ``await self.db.xxx(...)``／``select()`` 等异步 DB 代码。
"""

import asyncio

from app.models.user import Role


class UserRoleServiceAsyncMixin:
    """``*_async`` 方法 = sync 静态方法 + ``asyncio.to_thread``（``self.db`` 为 Session）。"""

    async def assign_role_async(self, user_id: int, role_id: int) -> bool:
        """为用户分配角色（异步桥接），含幂等性校验。"""
        return await asyncio.to_thread(self.assign_role, self.db, user_id, role_id)

    async def remove_role_async(self, user_id: int, role_id: int) -> bool:
        """移除用户的角色分配（异步桥接）。"""
        return await asyncio.to_thread(self.remove_role, self.db, user_id, role_id)

    async def get_user_roles_async(self, user_id: int) -> list[Role]:
        """查询用户的所有角色（异步桥接）。"""
        return await asyncio.to_thread(self.get_user_roles, self.db, user_id)
