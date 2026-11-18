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

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, select
from sqlalchemy.orm import selectinload

from app.db.database import Base, async_get_db, get_db
from app.db.smart_sync import DatabaseSyncTool
from app.utils.jwt_utils import get_password_hash
from app.models.project import Project
from app.models.user import User
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
async def async_db(_sync_schema_setup, sync_backed_async_db):
    """异步测试会话 — 同步事务的异步外观壳（R2-1 阶段四）。

    端点层已全面切 `get_db`（同步 Session），双轨 async engine 会带来两个问题：
    1. 端点用同步会话看不到 async 事务内数据（未 commit）；
    2. 把 async 连接跨线程交给 `asyncio.to_thread` 会导致参数绑定错乱。

    因此与 `tests/conftest.py` 对齐，统一用 `_SyncBackedAsyncSession` 包同一
    同步事务：async fixture 的写入与同步端点的读取共享同一 Session。
    """
    return sync_backed_async_db


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
    """异步 HTTP 客户端 — override get_db + async_get_db。

    用于未认证场景测试：oauth2_scheme 在 get_current_user 之前抛 401。
    R2-1 阶段四后端点统一用同步 `get_db`，这里指向 async_db 底层同步会话。
    """
    from app.main import app

    async def override_async_get_db():
        yield async_db

    async def override_get_db():
        yield async_db._sync

    app.dependency_overrides[async_get_db] = override_async_get_db
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    # 设置 Origin 头模拟真实浏览器，使 CSRF 中间件 Origin/Referer 校验通过
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:5173"},
    ) as client:
        yield client
    app.dependency_overrides.pop(async_get_db, None)
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture(scope="function")
async def async_auth_client(async_db, async_test_user):
    """异步 HTTP 客户端 — override get_db + async_get_db + get_current_user。

    用于普通用户认证场景：绕过 get_current_user 的同步 DB 查询。
    R2-1 阶段四后端点统一用同步 `get_db`，这里指向 async_db 底层同步会话。
    """
    from app.main import app
    from app.api.v1.endpoints.auth_deps import get_current_user

    async def override_async_get_db():
        yield async_db

    async def override_get_db():
        yield async_db._sync

    async def override_get_current_user():
        return async_test_user

    app.dependency_overrides[async_get_db] = override_async_get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    # 设置 Origin 头模拟真实浏览器，使 CSRF 中间件 Origin/Referer 校验通过
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Origin": "http://localhost:5173"},
    ) as client:
        yield client
    app.dependency_overrides.pop(async_get_db, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
