"""测试任务 API 权限校验测试——验证 _verify_project_access / _verify_task_access。
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from tests.helpers import (
    assertResponseSuccess,
    assertResponseForbidden,
    assertResponseNotFound,
)


@pytest.fixture(scope="function")
def myAuthHeaders(testUser):
    from app.utils.jwt_utils import create_access_token

    token = create_access_token({"sub": str(testUser.id), "username": testUser.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def otherUser(db: Session):
    from app.models.user import User
    from app.utils.jwt_utils import get_password_hash

    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"other_user_{suffix}",
        email=f"other_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
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
def otherProject(db: Session, otherUser):
    from app.models.project import Project

    project = Project(
        name=f"other_project_{uuid.uuid4().hex[:8]}",
        user_id=otherUser.id,
        description="other user project",
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
def taskInOtherProject(db: Session, otherProject, otherUser):
    from app.models.test_task import TestTask

    task = TestTask(
        project_id=otherProject.id,
        task_name=f"task_other_{uuid.uuid4().hex[:8]}",
        case_ids=[],
        executor_id=otherUser.id,
        status=0,
        total_count=0,
    )
    db.add(task)
    db.flush()
    yield task

    try:
        db.query(TestTask).filter(TestTask.id == task.id).delete()
        db.flush()
    except Exception:
        db.rollback()


class TestCreateTaskPermission:
    """POST /api/v1/test_task/ 的权限校验。"""

    def test_create_with_other_project_returns_403(
        self, client, myAuthHeaders, otherProject
    ):
        response = client.post(
            "/api/v1/test_task/",
            json={
                "project_id": otherProject.id,
                "task_name": f"steal_{uuid.uuid4().hex[:8]}",
                "case_ids": [],
            },
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)

    def test_create_with_own_project_succeeds(
        self, client, myAuthHeaders, testProject
    ):
        response = client.post(
            "/api/v1/test_task/",
            json={
                "project_id": testProject.id,
                "task_name": f"own_{uuid.uuid4().hex[:8]}",
                "case_ids": [],
            },
            headers=myAuthHeaders,
        )
        data = assertResponseSuccess(response)
        assert "task_id" in data.get("data", data)


class TestGetTaskPermission:
    """GET /api/v1/test_task/{task_id} 的权限校验。"""

    def test_get_other_project_task_returns_403(
        self, client, myAuthHeaders, taskInOtherProject
    ):
        response = client.get(
            f"/api/v1/test_task/{taskInOtherProject.id}",
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)

    def test_get_nonexistent_task_returns_404(self, client, myAuthHeaders):
        response = client.get(
            "/api/v1/test_task/99999",
            headers=myAuthHeaders,
        )
        assertResponseNotFound(response)


class TestListTaskPermission:
    """GET /api/v1/test_task/ 的权限校验和筛选。"""

    def test_list_other_project_returns_403(
        self, client, myAuthHeaders, otherProject
    ):
        response = client.get(
            f"/api/v1/test_task/?project_id={otherProject.id}",
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)

    def test_list_without_project_excludes_other_user_tasks(
        self, client, myAuthHeaders, db: Session, testProject, testUser, taskInOtherProject
    ):
        from app.models.test_task import TestTask

        own_task = TestTask(
            project_id=testProject.id,
            task_name=f"task_own_{uuid.uuid4().hex[:8]}",
            case_ids=[],
            executor_id=testUser.id,
            status=0,
            total_count=0,
        )
        db.add(own_task)
        db.flush()

        response = client.get("/api/v1/test_task/", headers=myAuthHeaders)
        data = assertResponseSuccess(response)
        task_ids = {item["id"] for item in data["items"]}

        assert own_task.id in task_ids
        assert taskInOtherProject.id not in task_ids

    def test_list_filters_zero_status(
        self, client, myAuthHeaders, db: Session, testProject, testUser
    ):
        from app.models.test_task import TestTask

        waiting_task = TestTask(
            project_id=testProject.id,
            task_name=f"task_waiting_{uuid.uuid4().hex[:8]}",
            case_ids=[],
            executor_id=testUser.id,
            status=0,
            total_count=0,
        )
        running_task = TestTask(
            project_id=testProject.id,
            task_name=f"task_running_{uuid.uuid4().hex[:8]}",
            case_ids=[],
            executor_id=testUser.id,
            status=1,
            total_count=0,
        )
        db.add_all([waiting_task, running_task])
        db.flush()

        response = client.get(
            f"/api/v1/test_task/?project_id={testProject.id}&task_status=0",
            headers=myAuthHeaders,
        )
        data = assertResponseSuccess(response)
        task_ids = {item["id"] for item in data["items"]}

        assert waiting_task.id in task_ids
        assert running_task.id not in task_ids
        assert all(item["status"] == 0 for item in data["items"])


class TestStartTaskPermission:
    """POST /api/v1/test_task/{task_id}/start 的权限校验。"""

    def test_start_other_project_task_returns_403(
        self, client, myAuthHeaders, taskInOtherProject
    ):
        response = client.post(
            f"/api/v1/test_task/{taskInOtherProject.id}/start",
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)


class TestDeleteTaskPermission:
    """DELETE /api/v1/test_task/{task_id} 的权限校验。"""

    def test_delete_other_project_task_returns_403(
        self, client, myAuthHeaders, taskInOtherProject
    ):
        response = client.delete(
            f"/api/v1/test_task/{taskInOtherProject.id}",
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)


class TestRunTaskPermission:
    """POST /api/v1/test_task/{task_id}/run 的权限校验。"""

    def test_run_other_project_task_returns_403(
        self, client, myAuthHeaders, taskInOtherProject
    ):
        response = client.post(
            f"/api/v1/test_task/{taskInOtherProject.id}/run",
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)


class TestSummaryPermission:
    """GET /api/v1/test_task/{task_id}/summary 的权限校验。"""

    def test_summary_other_project_task_returns_403(
        self, client, myAuthHeaders, taskInOtherProject
    ):
        response = client.get(
            f"/api/v1/test_task/{taskInOtherProject.id}/summary",
            headers=myAuthHeaders,
        )
        assertResponseForbidden(response)
