"""用户-角色关联服务异步 Mixin。

从 sync 版本（UserRoleService 静态方法）镜像出 async 实例方法，供 async
端点直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync 静态方法共存（hybrid 模式），sync 调用方继续用静态方法；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - 用户/角色存在性校验直接用 async 查询，不复用 sync 静态方法（涉及 db）；
    - 方法名加 _async 后缀避免与 sync 静态方法冲突；
    - self.db 在运行时为 AsyncSession 实例。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = UserRoleService(db)  # db 为 AsyncSession
        await service.assign_role_async(user_id, role_id)
"""
from sqlalchemy import select, delete, and_

from app.models.user import User, Role, user_role
from app.core.exception import BaseAPIException


class UserRoleServiceAsyncMixin:
    """用户-角色关联服务异步操作 Mixin，供 UserRoleService 继承。

    要求 self.db 为 AsyncSession 实例。
    """

    async def assign_role_async(self, user_id: int, role_id: int) -> bool:
        """为用户分配角色（异步版本），含幂等性校验。

        Raises:
            BaseAPIException: 用户不存在(404)、角色不存在(404)、角色已分配(400)。
        """
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        if not user_result.scalars().first():
            raise BaseAPIException("用户不存在", code=404)

        role_result = await self.db.execute(
            select(Role).where(Role.id == role_id)
        )
        if not role_result.scalars().first():
            raise BaseAPIException("角色不存在", code=404)

        existing = await self.db.execute(
            select(user_role).where(
                and_(
                    user_role.c.user_id == user_id,
                    user_role.c.role_id == role_id,
                )
            )
        )
        if existing.scalars().first():
            raise BaseAPIException("角色已分配", code=400)

        await self.db.execute(
            user_role.insert().values(user_id=user_id, role_id=role_id)
        )
        await self.db.commit()
        return True

    async def remove_role_async(self, user_id: int, role_id: int) -> bool:
        """移除用户的角色分配（异步版本）。

        Raises:
            BaseAPIException: 角色分配不存在(404)。
        """
        result = await self.db.execute(
            delete(user_role).where(
                and_(
                    user_role.c.user_id == user_id,
                    user_role.c.role_id == role_id,
                )
            )
        )
        await self.db.commit()
        if result.rowcount == 0:
            raise BaseAPIException("角色分配不存在", code=404)
        return True
