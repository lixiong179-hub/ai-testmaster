import os
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.database import Base, get_db
from app.utils.jwt_utils import create_access_token, get_password_hash

os.environ.setdefault("ENVIRONMENT", "test")

_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.replace("/ai_testmaster", "/ai_testmaster_test")
    if "/ai_testmaster" in settings.DATABASE_URL
    else settings.DATABASE_URL,
)


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
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db(testEngine) -> Session:
    connection = testEngine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restartSavepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
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
    token = create_access_token({"sub": str(testUser.username)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def adminAuthHeaders(testAdminUser):
    token = create_access_token({"sub": str(testAdminUser.username)})
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
