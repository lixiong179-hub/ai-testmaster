import os
import warnings
import asyncio
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.database import Base, get_db
from app.db.smart_sync import DatabaseSyncTool
from app.utils.jwt_utils import create_access_token, get_password_hash

os.environ.setdefault("ENVIRONMENT", "test")

# Skip broken test files that reference non-existent modules
_tests_dir = os.path.dirname(os.path.abspath(__file__))
collect_ignore_glob = [
    os.path.join(_tests_dir, "test_browser_*.py"),
    os.path.join(_tests_dir, "test_element_locator_*.py"),
    os.path.join(_tests_dir, "test_execution_engine_*.py"),
]

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
