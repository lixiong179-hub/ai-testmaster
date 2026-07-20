import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient


def assertResponseSuccess(response: Any, expectedStatus: int = 200) -> dict:
    assert response.status_code == expectedStatus, (
        f"Expected status {expectedStatus}, got {response.status_code}: {response.text}"
    )
    data = response.json()
    return data


def assertResponseError(response: Any, expectedStatus: int = 400) -> dict:
    assert response.status_code == expectedStatus, (
        f"Expected status {expectedStatus}, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert "detail" in data or "message" in data, (
        f"Error response missing detail/message field: {data}"
    )
    return data


def assertResponseNotFound(response: Any) -> dict:
    return assertResponseError(response, expectedStatus=404)


def assertResponseUnauthorized(response: Any) -> dict:
    return assertResponseError(response, expectedStatus=401)


def assertResponseForbidden(response: Any) -> dict:
    return assertResponseError(response, expectedStatus=403)


def assertFieldValue(data: dict, field: str, expected: Any) -> None:
    actual = data.get(field)
    assert actual == expected, (
        f"Field '{field}': expected {expected!r}, got {actual!r}"
    )


def assertFieldExists(data: dict, field: str) -> None:
    assert field in data, f"Field '{field}' not found in response: {list(data.keys())}"


def assertPaginatedResponse(data: dict, expectItems: bool = True) -> None:
    assertFieldExists(data, "items")
    assertFieldExists(data, "total")
    assert isinstance(data["items"], list), f"'items' should be list, got {type(data['items'])}"
    assert isinstance(data["total"], int), f"'total' should be int, got {type(data['total'])}"
    if expectItems:
        assert data["total"] > 0, "Expected non-empty paginated result"


def createTestUser(
    db: Session,
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: str = "Test@123456",
    isActive: bool = True,
    isSuperuser: bool = False,
) -> Any:
    from app.models.user import User
    from app.utils.jwt_utils import get_password_hash

    uniqueId = uuid.uuid4().hex[:8]
    user = User(
        username=username or f"helper_user_{uniqueId}",
        email=email or f"helper_{uniqueId}@test.com",
        password_hash=get_password_hash(password),
        is_active=isActive,
        is_superuser=isSuperuser,
    )
    db.add(user)
    db.flush()
    return user


def createTestProject(
    db: Session,
    userId: int,
    name: Optional[str] = None,
    description: str = "helper test project",
    status: int = 1,
    projectType: str = "web",
) -> Any:
    from app.models.project import Project

    uniqueId = uuid.uuid4().hex[:8]
    project = Project(
        name=name or f"helper_project_{uniqueId}",
        user_id=userId,
        description=description,
        status=status,
        project_type=projectType,
    )
    db.add(project)
    db.flush()
    return project


def createTestTestCase(
    db: Session,
    projectId: int,
    title: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    from app.models.test_case import TestCase

    uniqueId = uuid.uuid4().hex[:8]
    # TestCase 多个 DB 列为 NOT NULL (case_no/module/precondition/steps_json/
    # expected_result/priority/case_type), 需提供默认值；调用方 kwargs 优先
    defaults = {
        "case_no": f"helper_case_{uniqueId}",
        "module": "helper_module",
        "precondition": "",
        "steps_json": [],
        "expected_result": "",
        "priority": 2,
        "case_type": "manual",
    }
    defaults.update(kwargs)
    testCase = TestCase(
        title=title or f"helper_testcase_{uniqueId}",
        project_id=projectId,
        **defaults,
    )
    db.add(testCase)
    db.flush()
    return testCase


def createTestTestPoint(
    db: Session,
    projectId: int,
    name: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    from app.models.test_point import TestPoint

    uniqueId = uuid.uuid4().hex[:8]
    testPoint = TestPoint(
        name=name or f"helper_testpoint_{uniqueId}",
        project_id=projectId,
        **kwargs,
    )
    db.add(testPoint)
    db.flush()
    return testPoint


def cleanupTableByIds(db: Session, modelClass: Any, ids: list[int]) -> None:
    if not ids:
        return
    try:
        db.query(modelClass).filter(modelClass.id.in_(ids)).delete(synchronize_session="fetch")
        db.flush()
    except Exception:
        db.rollback()


def cleanupTableByName(db: Session, modelClass: Any, nameField: str, namePrefix: str) -> int:
    try:
        count = db.query(modelClass).filter(
            getattr(modelClass, nameField).like(f"{namePrefix}%")
        ).delete(synchronize_session="fetch")
        db.flush()
        return count
    except Exception:
        db.rollback()
        return 0


def cleanupAllHelperData(db: Session) -> None:
    from app.models.test_case import TestCase
    from app.models.test_point import TestPoint
    from app.models.project import Project
    from app.models.user import User

    for model, field in [
        (TestCase, "title"),
        (TestPoint, "name"),
        (Project, "name"),
    ]:
        cleanupTableByName(db, model, field, "helper_")
    cleanupTableByName(db, User, "username", "helper_user_")


def loginAndGetToken(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data["access_token"]


def getAuthHeaders(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
