import os
# 测试环境放宽 captcha 频率限制 (默认 10/分钟, 测试批量执行需要更高)
os.environ.setdefault("CAPTCHA_RATE_LIMIT", "10000")
import uuid
import warnings
import asyncio
from contextlib import ExitStack
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.util.concurrency import greenlet_spawn
from httpx import AsyncClient, ASGITransport


class _SyncBackedAsyncSession:
    """轻量级 AsyncSession 替代品，委托给 sync Session。

    用于 sync TestClient 调用 async 端点的测试场景：
    async 端点使用 db.run_sync() / db.execute() / db.commit() 等，
    本包装器将这些调用委托给 sync db fixture 的 Session，
    使 async 端点可见 sync db 事务中的测试数据（test_user / real_project 等）。

    设计原因：SQLAlchemy 2.0 的 AsyncSession 不接受 sync Connection 作为 bind，
    且 db.run_sync() 要求 AsyncEngine；而测试数据在 sync db 事务内（未 commit），
    独立 async engine 的连接无法看到。通过 wrapper 委托给同一 sync Session 可解决。
    """

    def __init__(self, sync_session: Session) -> None:
        self._sync = sync_session

    async def run_sync(self, fn, *args, **kwargs):
        return await greenlet_spawn(fn, self._sync, *args, **kwargs)

    async def execute(self, stmt, *args, **kwargs):
        return await greenlet_spawn(self._sync.execute, stmt, *args, **kwargs)

    async def scalar(self, stmt, *args, **kwargs):
        return await greenlet_spawn(self._sync.scalar, stmt, *args, **kwargs)

    async def scalars(self, stmt, *args, **kwargs):
        result = await greenlet_spawn(self._sync.execute, stmt, *args, **kwargs)
        return result.scalars()

    async def commit(self):
        # commit → flush，保持与 sync db fixture 一致的事务隔离策略
        await greenlet_spawn(self._sync.flush)

    async def rollback(self):
        # no-op：由 db fixture 的 savepoint 机制处理回滚
        pass

    async def refresh(self, instance, *args, **kwargs):
        await greenlet_spawn(self._sync.refresh, instance, *args, **kwargs)

    async def flush(self, *args, **kwargs):
        await greenlet_spawn(self._sync.flush, *args, **kwargs)

    async def close(self):
        # 不关闭底层 sync session，由 db fixture 统一清理
        pass

    async def merge(self, instance, *args, **kwargs):
        return await greenlet_spawn(self._sync.merge, instance, *args, **kwargs)

    async def get(self, entity, ident, *args, **kwargs):
        return await greenlet_spawn(self._sync.get, entity, ident, *args, **kwargs)

    def add(self, instance, *args, **kwargs):
        self._sync.add(instance, *args, **kwargs)

    def add_all(self, instances):
        self._sync.add_all(instances)

    def delete(self, instance):
        self._sync.delete(instance)

    def query(self, *args, **kwargs):
        return self._sync.query(*args, **kwargs)

    @property
    def is_active(self):
        return self._sync.is_active

    @property
    def in_transaction(self):
        return self._sync.in_transaction

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


@pytest.fixture(autouse=True)
def resetAiSemaphore():
    """每个测试前重置 AI 生成信号量单例，避免前序用例残留计数影响后续用例。"""
    from app.utils.ai_concurrency import reset_ai_generation_semaphore
    reset_ai_generation_semaphore()
    yield


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
def sync_backed_async_db(db):
    """为 async 测试提供与 sync db 共享事务的 AsyncSession 包装。

    直接调用 async service 函数时，sync db 的 Session 无法 await db.execute()，
    用 _SyncBackedAsyncSession 包装后委托 greenlet_spawn 执行，保持与 sync db
    事务的数据可见性（testUser / testProject 等均在 sync db 事务内）。
    """
    return _SyncBackedAsyncSession(db)


@pytest.fixture(scope="function")
def cleanupTracker():
    tracker = {"tables": [], "ids": {}}

    yield tracker

    tracker.clear()


@pytest.fixture(scope="function")
def client(db):
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from sqlalchemy.orm import Session as SyncSession
    from app.main import app
    from app.db import database as db_module
    import sys

    def overrideGetDb():
        try:
            yield db
        finally:
            pass

    async def overrideAsyncGetDb():
        # 关键：用 _SyncBackedAsyncSession 包装 sync db 的 Session，
        # 使 async 端点的 db.run_sync() / db.execute() / db.commit() 等
        # 委托给 sync db，从而可见 sync db 事务中的 test_user/real_project 等数据。
        # commit → flush 已在 wrapper 内实现，保持事务隔离。
        yield _SyncBackedAsyncSession(db)

    _shared_session_ref = {"session": None}

    def _create_shared_session():
        """创建共享 db 连接的 sync Session，使端点内 PrimarySessionLocal()
        创建的独立会话也能可见 sync db 事务中的测试数据。

        关键设计：同一测试内多次调用 PrimarySessionLocal() 返回同一个 session 实例，
        确保前一次调用写入（flush）的数据对后续调用的查询可见（同事务 + 同 identity map）。
        commit → flush、rollback → no-op、close → no-op，保持外层事务隔离不被破坏。
        实际事务由 db fixture 的外层 transaction.rollback() 统一清理。"""
        if _shared_session_ref["session"] is None:
            session = SyncSession(bind=db.connection())
            session.commit = session.flush
            session.rollback = lambda *a, **kw: None
            session.close = lambda *a, **kw: None  # type: ignore[assignment]
            _shared_session_ref["session"] = session
        return _shared_session_ref["session"]

    app.dependency_overrides[get_db] = overrideGetDb
    app.dependency_overrides[async_get_db] = overrideAsyncGetDb

    # 收集所有已加载模块中引用了 PrimarySessionLocal 的模块，
    # 统一 patch 为共享 db 连接，否则端点内 PrimarySessionLocal() 创建的独立会话
    # 看不到测试事务中的数据。覆盖阶段4 service 层 async 化所有迁移端点。
    _primary_session_local_modules = []
    for _mod in list(sys.modules.values()):
        if _mod is None:
            continue
        try:
            if getattr(_mod, "PrimarySessionLocal", None) is db_module.PrimarySessionLocal:
                _primary_session_local_modules.append(_mod.__name__)
        except Exception:
            continue

    _patch_managers = []
    _patch_managers.append(
        patch.object(db_module, "PrimarySessionLocal", side_effect=_create_shared_session)
    )
    for _mod_name in _primary_session_local_modules:
        _patch_managers.append(
            patch(f"{_mod_name}.PrimarySessionLocal", side_effect=_create_shared_session)
        )

    with ExitStack() as _stack:
        for _mgr in _patch_managers:
            _stack.enter_context(_mgr)
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(async_get_db, None)


@pytest.fixture(scope="function")
def testUser(db):
    from app.models.user import User

    # 使用 UUID 后缀避免全量回归时多测试创建同名用户导致 MySQL 死锁
    uniqueSuffix = f"{os.getenv('PYTEST_XDIST_WORKER', '0')}_{uuid.uuid4().hex[:8]}"
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

    # 使用 UUID 后缀避免全量回归时多测试创建同名用户导致 MySQL 死锁
    uniqueSuffix = f"{os.getenv('PYTEST_XDIST_WORKER', '0')}_{uuid.uuid4().hex[:8]}"
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
    from unittest.mock import patch
    from sqlalchemy.orm import Session as SyncSession

    async def override_async_get_db():
        yield async_db

    app.dependency_overrides[async_get_db] = override_async_get_db

    _shared_async_session_ref = {"session": None}

    def _create_shared_sync_session():
        """为 async 测试中调用 PrimarySessionLocal() 的端点提供共享 sync session。
        复用 async_db 的底层 sync connection，确保可见 async_db 事务内的测试数据。"""
        if _shared_async_session_ref["session"] is None:
            sync_conn = async_db.sync_session.connection()
            session = SyncSession(bind=sync_conn)
            session.commit = session.flush
            session.rollback = lambda *a, **kw: None
            session.close = lambda *a, **kw: None
            _shared_async_session_ref["session"] = session
        return _shared_async_session_ref["session"]

    import sys
    from app.db import database as db_module
    _patch_targets = []
    for _mod in list(sys.modules.values()):
        if _mod is None:
            continue
        try:
            if getattr(_mod, "PrimarySessionLocal", None) is db_module.PrimarySessionLocal:
                _patch_targets.append(_mod.__name__)
        except Exception:
            continue

    _patch_mgrs = [patch.object(db_module, "PrimarySessionLocal", side_effect=_create_shared_sync_session)]
    for _mod_name in _patch_targets:
        _patch_mgrs.append(patch(f"{_mod_name}.PrimarySessionLocal", side_effect=_create_shared_sync_session))

    with ExitStack() as _stack:
        for _mgr in _patch_mgrs:
            _stack.enter_context(_mgr)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    app.dependency_overrides.pop(async_get_db, None)


@pytest_asyncio.fixture(scope="function")
async def async_auth_client(async_db, async_test_user):
    """异步 HTTP 客户端 — override async_get_db + get_current_user（普通用户）。"""
    from app.main import app
    from app.api.v1.endpoints.auth_deps import get_current_user
    from unittest.mock import patch
    from sqlalchemy.orm import Session as SyncSession

    async def override_async_get_db():
        yield async_db

    async def override_get_current_user():
        return async_test_user

    app.dependency_overrides[async_get_db] = override_async_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    _shared_async_session_ref = {"session": None}

    def _create_shared_sync_session():
        """为 async 测试中调用 PrimarySessionLocal() 的端点提供共享 sync session。"""
        if _shared_async_session_ref["session"] is None:
            sync_conn = async_db.sync_session.connection()
            session = SyncSession(bind=sync_conn)
            session.commit = session.flush
            session.rollback = lambda *a, **kw: None
            session.close = lambda *a, **kw: None
            _shared_async_session_ref["session"] = session
        return _shared_async_session_ref["session"]

    import sys
    from app.db import database as db_module
    _patch_targets = []
    for _mod in list(sys.modules.values()):
        if _mod is None:
            continue
        try:
            if getattr(_mod, "PrimarySessionLocal", None) is db_module.PrimarySessionLocal:
                _patch_targets.append(_mod.__name__)
        except Exception:
            continue

    _patch_mgrs = [patch.object(db_module, "PrimarySessionLocal", side_effect=_create_shared_sync_session)]
    for _mod_name in _patch_targets:
        _patch_mgrs.append(patch(f"{_mod_name}.PrimarySessionLocal", side_effect=_create_shared_sync_session))

    with ExitStack() as _stack:
        for _mgr in _patch_mgrs:
            _stack.enter_context(_mgr)
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
    from unittest.mock import patch
    from sqlalchemy.orm import Session as SyncSession

    async def override_async_get_db():
        yield async_db

    async def override_get_current_user():
        return async_admin_user

    app.dependency_overrides[async_get_db] = override_async_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    _shared_async_session_ref = {"session": None}

    def _create_shared_sync_session():
        """为 async 测试中调用 PrimarySessionLocal() 的端点提供共享 sync session。"""
        if _shared_async_session_ref["session"] is None:
            sync_conn = async_db.sync_session.connection()
            session = SyncSession(bind=sync_conn)
            session.commit = session.flush
            session.rollback = lambda *a, **kw: None
            session.close = lambda *a, **kw: None
            _shared_async_session_ref["session"] = session
        return _shared_async_session_ref["session"]

    import sys
    from app.db import database as db_module
    _patch_targets = []
    for _mod in list(sys.modules.values()):
        if _mod is None:
            continue
        try:
            if getattr(_mod, "PrimarySessionLocal", None) is db_module.PrimarySessionLocal:
                _patch_targets.append(_mod.__name__)
        except Exception:
            continue

    _patch_mgrs = [patch.object(db_module, "PrimarySessionLocal", side_effect=_create_shared_sync_session)]
    for _mod_name in _patch_targets:
        _patch_mgrs.append(patch(f"{_mod_name}.PrimarySessionLocal", side_effect=_create_shared_sync_session))

    with ExitStack() as _stack:
        for _mgr in _patch_mgrs:
            _stack.enter_context(_mgr)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    app.dependency_overrides.pop(async_get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束时清理 async_primary_engine 连接池。

    避免事件循环关闭后 pool_pre_ping 触发
    `RuntimeError: Event loop is closed`（L-1 修复）。

    async_primary_engine 是 app.db.database._engine 的模块级单例，
    即使测试中 override 了 async_get_db，引擎对象仍会被导入创建。
    显式 dispose 确保连接池中的连接在新事件循环中干净关闭。
    """
    import asyncio
    try:
        from app.db.database._engine import async_primary_engine
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(async_primary_engine.dispose())
        finally:
            loop.close()
    except Exception:
        # 引擎未创建或已 dispose，忽略
        pass
