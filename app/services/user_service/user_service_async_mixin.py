"""用户服务异步 Mixin。

从 sync 版本（UserService 静态方法）镜像出 async 实例方法，供 async 端点
直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync 静态方法共存（hybrid 模式），sync 调用方继续用静态方法；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - 纯计算方法（verify_password/get_password_hash）复用 sync 静态方法，不重复实现；
    - 方法名加 _async 后缀避免与 sync 静态方法冲突；
    - self.db 在运行时为 AsyncSession 实例。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = UserService(db)  # db 为 AsyncSession
        user = await service.create_user_async(user_in)
"""
from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.exception import BaseAPIException


class UserServiceAsyncMixin:
    """用户服务异步操作 Mixin，供 UserService 继承。

    要求 self.db 为 AsyncSession 实例。纯计算方法（密码哈希/校验）
    复用 UserService 的 sync 静态方法，避免重复实现。
    """

    async def create_user_async(self, user_in: UserCreate | dict) -> User:
        """创建新用户（异步版本），含用户名和邮箱唯一性校验。

        Raises:
            BaseAPIException: 用户名已存在(400)、邮箱已存在(400)、创建失败(400)。
        """
        if isinstance(user_in, dict):
            user_in = UserCreate(**user_in)

        # 校验用户名唯一性
        existing = await self.db.execute(
            select(User).where(User.username == user_in.username)
        )
        if existing.scalars().first():
            raise BaseAPIException("用户名已存在", code=400)

        # 邮箱非必填字段，填写时需校验唯一性
        if user_in.email:
            email_existing = await self.db.execute(
                select(User).where(User.email == user_in.email)
            )
            if email_existing.scalars().first():
                raise BaseAPIException("邮箱已存在", code=400)

        # 密码哈希处理，明文密码不落库（复用 sync 静态方法）
        hashed_password = self.get_password_hash(user_in.password)
        db_user = User(
            username=user_in.username,
            password_hash=hashed_password,
            email=user_in.email,
            phone=user_in.phone,
        )
        self.db.add(db_user)
        try:
            await self.db.commit()
            await self.db.refresh(db_user)
        except IntegrityError:
            # 并发场景下可能突破前置校验，通过数据库约束兜底
            await self.db.rollback()
            raise BaseAPIException("创建用户失败", code=400)
        return db_user

    async def authenticate_user_async(
        self, username: str, password: str
    ) -> Optional[User]:
        """用户认证（异步版本），验证用户名和密码。

        Returns:
            认证成功返回 User 实例，用户不存在或密码错误返回 None。

        Raises:
            BaseAPIException: 用户已被禁用(403)。
        """
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalars().first()
        if not user:
            return None
        # 密码校验为纯计算，复用 sync 静态方法
        if not self.verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            raise BaseAPIException("用户已被禁用", code=403)
        return user

    async def get_user_by_id_async(self, user_id: int) -> Optional[User]:
        """根据用户ID查询用户（异步版本）。"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalars().first()

    async def update_user_async(
        self, user_id: int, user_in: UserUpdate | dict
    ) -> User:
        """更新用户信息（异步版本），仅修改传入字段。

        Raises:
            BaseAPIException: 用户不存在(404)、更新失败(400)。
        """
        if isinstance(user_in, dict):
            user_in = UserUpdate(**user_in)

        user = await self.get_user_by_id_async(user_id)
        if not user:
            raise BaseAPIException("用户不存在", code=404)

        update_data = user_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        try:
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError:
            await self.db.rollback()
            raise BaseAPIException("更新用户失败", code=400)
        return user

    async def delete_user_async(self, user_id: int) -> bool:
        """删除用户及其角色关联关系（异步版本）。

        Raises:
            BaseAPIException: 用户不存在(404)。
        """
        from app.models.user import user_role as user_role_table

        user = await self.get_user_by_id_async(user_id)
        if not user:
            raise BaseAPIException("用户不存在", code=404)
        await self.db.execute(
            delete(user_role_table).where(user_role_table.c.user_id == user_id)
        )
        await self.db.delete(user)
        await self.db.commit()
        return True

    async def get_users_async(
        self, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """分页查询用户列表（异步版本）。"""
        result = await self.db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
