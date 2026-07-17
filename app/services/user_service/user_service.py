
"""用户服务 - 处理用户认证、密码管理与CRUD操作。

职责:
    - 密码验证与哈希生成
    - 用户创建（含唯一性校验）
    - 用户认证（登录验证）
    - 用户信息查询与更新
    - 用户删除（级联清理角色关联）

使用场景:
    - 登录认证流程中调用authenticate_user
    - 用户管理页面调用CRUD方法
    - 权限校验前通过get_user_by_id获取用户信息

设计意图:
    Hybrid 模式：sync 调用方继续使用静态方法（db: Session 由调用方传入），
    async 调用方通过实例化 UserService(db: AsyncSession) 调用 *_async 方法。
    纯计算方法（verify_password/get_password_hash）保持静态，供 sync/async 复用。
"""
from typing import Optional, List, Union
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.exception import BaseAPIException
from app.services.user_service.user_service_async_mixin import UserServiceAsyncMixin

# bcrypt密码加密上下文，deprecated="auto"表示自动迁移旧哈希格式
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService(UserServiceAsyncMixin):
    """用户服务 - 处理用户认证、密码管理与CRUD操作。

    Hybrid 模式：
        - sync 调用：直接使用静态方法，例如 ``UserService.create_user(db, user_in)``
        - async 调用：实例化后调用 ``*_async`` 方法，例如
          ``await UserService(db).create_user_async(user_in)``，此时 db 必须为 AsyncSession。
    """

    def __init__(self, db: Optional[Union[Session, AsyncSession]] = None) -> None:
        """初始化服务实例。

        Args:
            db: 数据库会话。sync 静态方法不依赖此属性；async 实例方法
                要求传入 AsyncSession 实例。默认 None 允许在不持有 db 的
                场景下实例化（仅用于调用纯计算静态方法时）。
        """
        self.db = db

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证明文密码与哈希密码是否匹配。

        使用bcrypt算法进行安全比对，耗时恒定防止时序攻击。

        Args:
            plain_password: 用户输入的明文密码。
            hashed_password: 数据库中存储的bcrypt哈希值。

        Returns:
            密码匹配返回True，否则返回False。
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """生成密码的bcrypt哈希值，用于安全存储。

        Args:
            password: 待哈希的明文密码。

        Returns:
            bcrypt哈希字符串，包含算法标识、盐值和哈希结果。
        """
        return pwd_context.hash(password)

    @staticmethod
    def create_user(db: Session, user_in: UserCreate | dict) -> User:
        """创建新用户，含用户名和邮箱唯一性校验。

        创建流程:
            1. 参数适配（支持dict和Schema两种输入格式）
            2. 用户名唯一性校验
            3. 邮箱唯一性校验（邮箱非必填，填写时才校验）
            4. 密码哈希后存储
            5. 数据库写入，处理并发唯一约束冲突

        Args:
            db: 数据库会话，由调用方管理事务。
            user_in: 用户创建参数，支持UserCreate Schema或dict。

        Returns:
            创建成功的User ORM实例。

        Raises:
            BaseAPIException: 用户名已存在(400)、邮箱已存在(400)、
                创建失败(400，并发唯一约束冲突)。
        """
        # 支持dict和Schema两种输入格式，方便不同调用场景
        if isinstance(user_in, dict):
            user_in = UserCreate(**user_in)

        # 校验用户名唯一性
        existing_user = db.execute(
            select(User).where(
                User.username == user_in.username
            )
        )
        existing_user = existing_user.scalars().first()
        if existing_user:
            raise BaseAPIException("用户名已存在", code=400)

        # 邮箱非必填字段，填写时需校验唯一性
        if user_in.email:
            email_user = db.execute(
                select(User).where(User.email == user_in.email)
            ).scalars().first()
            if email_user:
                raise BaseAPIException("邮箱已存在", code=400)

        # 密码哈希处理，明文密码不落库
        hashed_password = UserService.get_password_hash(user_in.password)
        db_user = User(
            username=user_in.username,
            password_hash=hashed_password,
            email=user_in.email,
            phone=user_in.phone,
        )
        db.add(db_user)
        try:
            db.commit()
            db.refresh(db_user)
        except IntegrityError:
            # 并发场景下可能突破前置校验，通过数据库约束兜底
            db.rollback()
            raise BaseAPIException("创建用户失败", code=400)
        return db_user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """用户认证，验证用户名和密码是否正确。

        认证流程:
            1. 按用户名查询用户记录
            2. 验证密码哈希是否匹配
            3. 检查用户是否被禁用

        Args:
            db: 数据库会话。
            username: 用户名。
            password: 明文密码。

        Returns:
            认证成功返回User实例，用户不存在或密码错误返回None。

        Raises:
            BaseAPIException: 用户已被禁用(403)。

        Note:
            用户不存在和密码错误统一返回None，不区分具体原因，
            防止攻击者通过错误信息枚举有效用户名。
        """
        user = db.execute(select(User).where(User.username == username)).scalars().first()
        if not user:
            return None
        if not UserService.verify_password(password, user.password_hash):
            return None
        # 用户被禁用时抛出明确异常，与认证失败区分
        if not user.is_active:
            raise BaseAPIException("用户已被禁用", code=403)
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """根据用户ID查询用户。

        Args:
            db: 数据库会话。
            user_id: 用户唯一标识。

        Returns:
            User实例，不存在时返回None。
        """
        return db.execute(select(User).where(User.id == user_id)).scalars().first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """根据用户名查询用户。

        Args:
            db: 数据库会话。
            username: 用户名。

        Returns:
            User实例，不存在时返回None。
        """
        return db.execute(select(User).where(User.username == username)).scalars().first()

    @staticmethod
    def update_user(db: Session, user_id: int, user_in: UserUpdate | dict) -> User:
        """更新用户信息，仅修改传入的字段（部分更新）。

        使用model_dump(exclude_unset=True)实现部分更新，
        未传入的字段不会被置为None。

        Args:
            db: 数据库会话。
            user_id: 待更新的用户ID。
            user_in: 更新参数，支持UserUpdate Schema或dict。

        Returns:
            更新后的User实例。

        Raises:
            BaseAPIException: 用户不存在(404)、更新失败(400)。
        """
        # 参数适配
        if isinstance(user_in, dict):
            user_in = UserUpdate(**user_in)

        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise BaseAPIException("用户不存在", code=404)

        # exclude_unset=True确保只更新实际传入的字段
        update_data = user_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise BaseAPIException("更新用户失败", code=400)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """删除用户及其角色关联关系。"""
        from app.models.user import user_role as user_role_table
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise BaseAPIException("用户不存在", code=404)
        db.execute(delete(user_role_table).where(user_role_table.c.user_id == user_id))
        db.delete(user)
        db.commit()
        return True

    @staticmethod
    def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """分页查询用户列表。

        Args:
            db: 数据库会话。
            skip: 跳过的记录数，用于分页偏移。
            limit: 每页最大记录数，默认100。

        Returns:
            User实例列表。
        """
        return db.execute(select(User).offset(skip).limit(limit)).scalars().all()
