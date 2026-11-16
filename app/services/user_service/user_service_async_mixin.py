"""用户服务异步桥接 Mixin（R2-1 阶段三：会话层单范式收敛）。

单范式后 ``self.db`` 为**同步** ``Session``（端点 ``Depends(get_db)``），
本 Mixin 不再用 AsyncSession 重写一遍 SQL，只保留 ``*_async`` 方法名做兼容：
把同名 sync 静态方法（``UserService.create_user`` 等）丢进工作线程执行。

约定：
    - 禁止在本文件出现 ``await self.db.xxx(...)``／``select()`` 等异步 DB 代码；
    - 新增能力先扩展 sync 静态方法，再在此追加一行 ``asyncio.to_thread`` 桥接。
"""

import asyncio

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserServiceAsyncMixin:
    """``*_async`` 方法 = sync 静态方法 + ``asyncio.to_thread``（``self.db`` 为 Session）。"""

    async def create_user_async(self, user_in: UserCreate | dict) -> User:
        """创建新用户（异步桥接），含用户名/邮箱唯一性校验。"""
        return await asyncio.to_thread(self.create_user, self.db, user_in)

    async def authenticate_user_async(self, username: str, password: str) -> User | None:
        """用户认证（异步桥接），用户名不存在或密码错误返回 None。"""
        return await asyncio.to_thread(self.authenticate_user, self.db, username, password)

    async def get_user_by_id_async(self, user_id: int) -> User | None:
        """根据用户ID查询用户（异步桥接）。"""
        return await asyncio.to_thread(self.get_user_by_id, self.db, user_id)

    async def update_user_async(self, user_id: int, user_in: UserUpdate | dict) -> User:
        """更新用户信息（异步桥接），仅修改传入字段。"""
        return await asyncio.to_thread(self.update_user, self.db, user_id, user_in)

    async def delete_user_async(self, user_id: int) -> bool:
        """删除用户及其角色关联（异步桥接）。"""
        return await asyncio.to_thread(self.delete_user, self.db, user_id)

    async def get_users_async(self, skip: int = 0, limit: int = 100) -> list[User]:
        """分页查询用户列表（异步桥接）。"""
        return await asyncio.to_thread(self.get_users, self.db, skip, limit)
