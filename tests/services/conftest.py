"""tests/services 共享 async 测试 fixture。

为 tests/services/ 下的 async 服务测试提供 AsyncSession 基础设施。
与 tests/api/conftest.py 的 async_db 模式对齐：事务隔离 + savepoint +
commit→flush 改写，使 service 内的 commit 不破坏测试隔离。

fixture 清单:
    - _sync_schema_setup: 同步建表（session 级，async engine 复用表结构）
    - async_db: 事务隔离 AsyncSession（function 级）
    - async_test_user: 测试用户（function 级，selectinload 预加载 roles）
    - async_test_project: 测试项目（function 级）
    - async_client: 异步 HTTP 客户端，仅 override async_get_db（未认证场景）
    - async_auth_client: 异步 HTTP 客户端，override async_get_db + get_current_user（认证场景）

注意: tests/services/ 下的同步测试（如 TestRecordMetric 使用 sync SQLite
in-memory）不受影响 — 它们使用各自文件内定义的局部 db fixture，与本文件
的 async_db 互不冲突。
"""
import os
import warnings

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, event, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import Base, async_get_db
from app.db.smart_sync import DatabaseSyncTool
from app.db.database._engine import _to_async_url
from app.utils.jwt_utils import get_password_hash
from app.models.project import Project
from app.models.user import User, Role, user_role
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
    """异步测试会话 — 事务隔离策略与 tests/api/conftest.py 对齐。

    1. 外层事务包裹整个测试，结束 rollback 不落库
    2. session.commit 改写为 flush，使 service 内的 commit 不破坏隔离
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
    user = User(
        username="async_test_user",
        email="async_test@test.com",
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(user)
    await async_db.flush()
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
