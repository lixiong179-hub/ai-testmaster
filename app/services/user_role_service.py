"""用户与角色核心服务模块 - 提供用户认证、CRUD及角色管理能力。

本模块包含用户服务和角色服务两个核心类，负责平台中用户账户的
创建、认证、更新、删除，以及角色的全生命周期管理。密码安全
通过passlib的bcrypt方案实现。

核心类:
    - UserService: 用户服务，处理用户认证与CRUD操作
    - RoleService: 角色服务，处理角色CRUD与权限分配

依赖关系:
    - app.models.user: User/Role/user_role ORM模型
    - app.schemas.user: 请求参数校验Schema
    - passlib.context.CryptContext: bcrypt密码哈希
    - sqlalchemy: 数据库查询与事务管理

设计说明:
    采用静态方法设计，服务层不持有状态，数据库会话由调用方传入，
    符合无状态服务原则，便于测试和并发调用。
"""
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from app.models.user import User, Role, user_role
from app.schemas.user import UserCreate, UserUpdate, RoleCreate, RoleUpdate
from app.core.exception import BaseAPIException

# bcrypt密码加密上下文，deprecated="auto"表示自动迁移旧哈希格式
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
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
        全部采用静态方法，服务不持有可变状态，数据库会话由调用方
        传入管理，确保事务边界清晰，避免长事务问题。
    """

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
        """删除用户及其角色关联关系。

        先清理user_role关联表中的记录，再删除用户本体，
        避免外键约束冲突。

        Args:
            db: 数据库会话。
            user_id: 待删除的用户ID。

        Returns:
            删除成功返回True。

        Raises:
            BaseAPIException: 用户不存在(404)。
        """
        user = UserService.get_user_by_id(db, user_id)
        if not user:
            raise BaseAPIException("用户不存在", code=404)

        # 先清理用户-角色关联，再删除用户，保证数据一致性
        db.execute(delete(user_role).where(user_role.c.user_id == user_id))
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


class RoleService:
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
