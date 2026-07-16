import os
import warnings
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from httpx import AsyncClient, ASGITransport

from app.core.config import settings
from app.db.database import Base, get_db, async_get_db
from app.db.database._engine import _to_async_url
from app.db.smart_sync import DatabaseSyncTool
from app.utils.jwt_utils import create_access_token, get_password_hash
from app.models.user import User, Role, user_role
from app.models.project import Project
import app.models  # noqa: F401 — ensure all models registered before create_all

os.environ.setdefault("ENVIRONMENT", "test")

_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.replace("/ai_testmaster", "/ai_testmaster_test")
    if "/ai_testmaster" in settings.DATABASE_URL
    else settings.DATABASE_URL,
)


@pytest.fixture(autouse=True)
def ensureEventLoop():
    created_loop = None
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        created_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(created_loop)

    yield

    if created_loop is not None:
        created_loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture(scope="session")
def testEngine():
    engine = create_engine(
        _TEST_DB_URL,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        connect_args={"init_command": "SET sql_mode='NO_ENGINE_SUBSTITUTION'"},
    )
    Base.metadata.create_all(engine)
    sync_tool = DatabaseSyncTool(engine=engine)
    sync_tool.sync_all_tables(Base, auto_fix=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(testEngine) -> Session:
    """测试数据库会话 — 自动事务隔离

    设计原理:
    1. 外层事务包裹整个测试，测试结束统一 rollback，数据不落库
    2. 覆写 session.commit() → session.flush()，使 service 层的 commit
       只刷新到外层事务内，不破坏隔离
    3. 覆写 session.rollback() → 仅回滚 savepoint，防止 app 层 rollback
       破坏外层事务
    4. after_transaction_end 事件自动重启 savepoint，兼容显式
       begin_nested() + commit()/rollback() 的用法
    """
    connection = testEngine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    session.commit = session.flush

    _savepoint = {"ref": session.begin_nested()}

    @event.listens_for(session, "after_transaction_end")
    def restartSavepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            _savepoint["ref"] = sess.begin_nested()

    _orig_rollback = session.rollback

    def _safe_rollback(*args, **kwargs):
        sp = _savepoint["ref"]
        if sp is not None and sp.is_active:
            sp.rollback()

    session.rollback = _safe_rollback

    yield session

    session.rollback = _orig_rollback
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="transaction already deassociated")
        transaction.rollback()
    session.close()
    connection.close()


@pytest.fixture(scope="function")
def db_session(db):
    return db


@pytest.fixture(scope="function")
def cleanupTracker():
    tracker = {"tables": [], "ids": {}}

    yield tracker

    tracker.clear()


@pytest.fixture(scope="function")
def client(db):
    from fastapi.testclient import TestClient
    from app.main import app

    def overrideGetDb():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = overrideGetDb
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def testUser(db):
    from app.models.user import User

    uniqueSuffix = os.getenv("PYTEST_XDIST_WORKER", "0")
    username = f"test_user_{uniqueSuffix}"
    email = f"test_{uniqueSuffix}@test.com"

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        db.delete(existing)
        db.flush()

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()

    yield user

    try:
        db.query(User).filter(User.id == user.id).delete()
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture(scope="function")
def testAdminUser(db):
    from app.models.user import User

    uniqueSuffix = os.getenv("PYTEST_XDIST_WORKER", "0")
    username = f"test_admin_{uniqueSuffix}"
    email = f"test_admin_{uniqueSuffix}@test.com"

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        db.delete(existing)
        db.flush()

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash("Admin@123456"),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    db.flush()

    # 确保 admin 角色存在并分配给该用户
    from app.models.user import Role, user_role

    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(name="admin", desc="管理员角色", permissions=["*"])
        db.add(admin_role)
        db.flush()
    if admin_role not in user.roles:
        user.roles.append(admin_role)
        db.flush()

    yield user

    try:
        db.query(User).filter(User.id == user.id).delete()
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture(scope="function")
def authHeaders(testUser):
    token = create_access_token({"sub": str(testUser.id), "username": testUser.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def adminAuthHeaders(testAdminUser):
    token = create_access_token({"sub": str(testAdminUser.id), "username": testAdminUser.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def testProject(db, testUser):
    from app.models.project import Project

    project = Project(
        name="test_project",
        user_id=testUser.id,
        description="test project description",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    yield project

    try:
        db.query(Project).filter(Project.id == project.id).delete()
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture(scope="function")
def test_project(testProject):
    return testProject


@pytest.fixture(scope="function")
def test_iteration(db, testProject):
    from app.models.iteration import Iteration

    iteration = Iteration(
        name="test_iteration",
        project_id=testProject.id,
        version="v1.0",
    )
    db.add(iteration)
    db.flush()

    yield iteration

    try:
        db.query(Iteration).filter(Iteration.id == iteration.id).delete()
        db.flush()
    except Exception:
        db.rollback()


# ============================================================================
# Async fixture（供 tests/ 根目录的 async endpoint 测试使用）
# 与 tests/api/conftest.py 的 async fixture 同源，复用 testEngine 已建表
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def async_db(testEngine):
    """异步测试会话 — 事务隔离策略与 sync db fixture 对齐。

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
    """创建测试用户（在 async_db 事务内），selectinload 预加载 roles。"""
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
    result = await async_db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user.id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture(scope="function")
async def async_admin_user(async_db):
    """创建带 admin 角色的测试用户（用于 _require_admin 场景）。"""
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
    await async_db.execute(
        user_role.insert().values(user_id=user.id, role_id=admin_role.id)
    )
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
    """异步 HTTP 客户端 — 仅 override async_get_db（未认证场景）。"""
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
    """异步 HTTP 客户端 — override async_get_db + get_current_user（普通用户）。"""
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
    """异步 HTTP 客户端 — override async_get_db + get_current_user（admin 用户）。"""
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
