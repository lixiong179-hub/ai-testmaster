"""tests/api 共享 async 测试 fixture。

提供 AsyncSession + 异步 HTTP 客户端基础设施，供 tests/api/ 下所有
async endpoint 测试复用。与全局 conftest.py 的同步 fixture 并存，互不冲突。

fixture 清单:
    - _sync_schema_setup: 同步建表（session 级，async engine 复用表结构）
    - async_db: 事务隔离 AsyncSession（function 级）
    - async_test_user: 测试用户（function 级，在 async_db 事务内）
    - async_test_project: 测试项目（function 级）
    - async_client: 异步 HTTP 客户端，仅 override async_get_db（未认证场景）
    - async_auth_client: 异步 HTTP 客户端，override async_get_db + get_current_user（认证场景）
    - async_admin_client: 异步 HTTP 客户端，override async_get_db + _require_admin（管理员场景）

设计原则:
    1. 事务隔离与同步 db fixture 策略对齐（savepoint + commit→flush 改写）
    2. async_client 用于 oauth2_scheme 层拦截的未认证测试（不查 DB）
    3. async_auth_client 绕过 get_current_user（async_db 事务对同步 session 不可见）
    4. 鉴权逻辑本身由 tests/api/test_auth_*.py 覆盖
"""
import os
import warnings

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.db.database import Base, async_get_db
from app.db.smart_sync import DatabaseSyncTool
from app.utils.jwt_utils import get_password_hash
from app.models.project import Project
from app.models.user import User, Role, user_role
from app.db.database._engine import _to_async_url
import app.models  # noqa: F401 — ensure all models registered

os.environ.setdefault("ENVIRONMENT", "test")

from app.core.config import settings

_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.replace("/ai_testmaster", "/ai_testmaster_test")
    if "/ai_testmaster" in settings.DATABASE_URL
    else settings.DATABASE_URL,
)


@pytest.fixture(scope="session")
def _sync_schema_setup():
    """同步建表，async engine 复用同一数据库的表结构。"""
    sync_engine = create_engine(_TEST_DB_URL, pool_pre_ping=True)
    Base.metadata.create_all(sync_engine)
    sync_tool = DatabaseSyncTool(engine=sync_engine)
    sync_tool.sync_all_tables(Base, auto_fix=True)
    yield sync_engine
    sync_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db(_sync_schema_setup):
    """异步测试会话 — 事务隔离策略与同步 db fixture 对齐。

    1. 外层事务包裹整个测试，结束 rollback 不落库
    2. session.commit 改写为 flush，使 endpoint 内的 commit 不破坏隔离
    3. savepoint 自动重启，兼容显式 begin_nested
    """
    async_engine = create_async_engine(
        _to_async_url(_TEST_DB_URL),
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
    )

    async with async_engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(bind=conn, expire_on_commit=False) as session:
            session.commit = session.flush

            _savepoint = {"ref": None}

            @event.listens_for(session.sync_session, "after_transaction_end")
            def restart_savepoint(sess, trans):
                if trans.nested and not trans._parent.nested:
                    _savepoint["ref"] = sess.begin_nested()

            _savepoint["ref"] = session.sync_session.begin_nested()

            yield session

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="transaction already deassociated"
                )
                await session.rollback()

    await async_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_test_user(async_db):
    """创建测试用户（在 async_db 事务内）。

    使用 selectinload 预加载 roles，避免后续 _require_admin 访问 user.roles 时
    触发 sync 懒加载（在 async 上下文中会抛 MissingGreenlet）。
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    user = User(
        username="async_test_user",
        email="async_test@test.com",
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(user)
    await async_db.flush()
    # 重新查询以 selectinload 预加载 roles（空列表，但避免懒加载）
    result = await async_db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture(scope="function")
async def async_admin_user(async_db):
    """创建带 admin 角色的测试用户（用于 _require_admin 场景）。

    使用 selectinload 重新查询用户以预加载 roles 关系，
    避免 _require_admin 在 async 上下文下访问 user.roles 时触发 sync 懒加载
    （会抛 MissingGreenlet）。
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    user = User(
        username="async_admin_user",
        email="async_admin@test.com",
        password_hash=get_password_hash("Admin@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(user)
    await async_db.flush()

    admin_role = (
        await async_db.execute(select(Role).where(Role.name == "admin"))
    ).scalar_one_or_none()
    if not admin_role:
        admin_role = Role(name="admin", desc="管理员角色", permissions=["*"])
        async_db.add(admin_role)
        await async_db.flush()
    # 通过 user_role 直接插入，避免触发 user.roles 的懒加载
    await async_db.execute(
        user_role.insert().values(user_id=user.id, role_id=admin_role.id)
    )
    await async_db.flush()

    # 重新查询用户，selectinload 预加载 roles
    result = await async_db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture(scope="function")
async def async_test_project(async_db, async_test_user):
    """创建测试项目。"""
    project = Project(
        name="async_test_project",
        user_id=async_test_user.id,
        description="async test project",
        status=1,
        project_type="web",
    )
    async_db.add(project)
    await async_db.flush()
    return project


@pytest_asyncio.fixture(scope="function")
async def async_client(async_db):
    """异步 HTTP 客户端 — 仅 override async_get_db。

    用于未认证场景测试：oauth2_scheme 在 get_current_user 之前抛 401。
    """
    from app.main import app

    async def override_async_get_db():
        yield async_db

    app.dependency_overrides[async_get_db] = override_async_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(async_get_db, None)


@pytest_asyncio.fixture(scope="function")
async def async_auth_client(async_db, async_test_user):
    """异步 HTTP 客户端 — override async_get_db + get_current_user。

    用于普通用户认证场景：绕过 get_current_user 的同步 DB 查询。
    """
    from app.main import app
    from app.api.v1.endpoints.auth_deps import get_current_user

    async def override_async_get_db():
        yield async_db

    async def override_get_current_user():
        return async_test_user

    app.dependency_overrides[async_get_db] = override_async_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(async_get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture(scope="function")
async def async_admin_client(async_db, async_admin_user):
    """异步 HTTP 客户端 — override async_get_db + get_current_user（admin 用户）。

    用于 _require_admin 场景：override get_current_user 返回 admin 用户，
    使 _require_admin 的角色检查通过。
    """
    from app.main import app
    from app.api.v1.endpoints.auth_deps import get_current_user

    async def override_async_get_db():
        yield async_db

    async def override_get_current_user():
        return async_admin_user

    app.dependency_overrides[async_get_db] = override_async_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(async_get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
