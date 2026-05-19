import pytest

from app.crud import iteration as iteration_crud
from app.services import iteration_service
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def iter_user(db):
    user = User(username="iter_api_user", email="iter_api@test.com", password_hash="hash", is_active=True)
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    try:
        db.query(Iteration).filter(
            Iteration.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture
def iter_project(db, iter_user):
    project = Project(name="iter_api_project", user_id=iter_user.id, description="iter api test", status=1, project_type="web")
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


class TestCreateIterationAPI:

    def test_create_success(self, client, authHeaders, testProject):
        payload = {
            "project_id": testProject.id,
            "name": "API创建迭代",
            "version": "v1.0",
        }
        response = client.post(
            "/api/v1/iteration/",
            json=payload,
            headers=authHeaders,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "API创建迭代"
        assert data["status"] == "draft"

    def test_create_duplicate_name(self, client, authHeaders, testProject):
        payload = {
            "project_id": testProject.id,
            "name": "重复迭代名",
        }
        client.post("/api/v1/iteration/", json=payload, headers=authHeaders)
        response = client.post("/api/v1/iteration/", json=payload, headers=authHeaders)
        assert response.status_code == 400

    def test_create_without_project_permission(self, client, authHeaders):
        payload = {
            "project_id": 99999,
            "name": "无权限迭代",
        }
        response = client.post("/api/v1/iteration/", json=payload, headers=authHeaders)
        assert response.status_code == 403

    def test_create_unauthenticated(self, client, testProject):
        payload = {
            "project_id": testProject.id,
            "name": "未认证迭代",
        }
        response = client.post("/api/v1/iteration/", json=payload)
        assert response.status_code == 401


class TestGetIterationsAPI:

    def test_list_iterations(self, client, authHeaders, db, testProject):
        iteration_crud.create_iteration(db=db, project_id=testProject.id, name="列表迭代")
        response = client.get(
            f"/api/v1/iteration/list/{testProject.id}",
            headers=authHeaders,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "items" in data
        assert "total" in data

    def test_list_unauthenticated(self, client, testProject):
        response = client.get(f"/api/v1/iteration/list/{testProject.id}")
        assert response.status_code == 401

    def test_list_no_permission(self, client, authHeaders):
        response = client.get("/api/v1/iteration/list/99999", headers=authHeaders)
        assert response.status_code == 403


class TestGetIterationDetailAPI:

    def test_get_detail(self, client, authHeaders, db, testProject):
        iteration = iteration_crud.create_iteration(db=db, project_id=testProject.id, name="详情迭代")
        response = client.get(
            f"/api/v1/iteration/{iteration.id}",
            headers=authHeaders,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "详情迭代"

    def test_get_nonexistent(self, client, authHeaders):
        response = client.get("/api/v1/iteration/99999", headers=authHeaders)
        assert response.status_code == 404


class TestUpdateIterationAPI:

    def test_update_name(self, client, authHeaders, db, testProject):
        iteration = iteration_crud.create_iteration(db=db, project_id=testProject.id, name="更新前")
        response = client.put(
            f"/api/v1/iteration/{iteration.id}",
            json={"name": "更新后"},
            headers=authHeaders,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "更新后"

    def test_update_status_to_in_pipeline(self, client, authHeaders, db, testProject):
        iteration = iteration_crud.create_iteration(db=db, project_id=testProject.id, name="状态测试")
        response = client.put(
            f"/api/v1/iteration/{iteration.id}",
            json={"status": "in_pipeline"},
            headers=authHeaders,
        )
        assert response.status_code == 200

    def test_update_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/iteration/99999",
            json={"name": "不存在"},
            headers=authHeaders,
        )
        assert response.status_code == 404


class TestDeleteIterationAPI:

    def test_delete_success(self, client, authHeaders, db, testProject):
        iteration = iteration_crud.create_iteration(db=db, project_id=testProject.id, name="删除迭代")
        response = client.delete(
            f"/api/v1/iteration/{iteration.id}",
            headers=authHeaders,
        )
        assert response.status_code == 200

    def test_delete_nonexistent(self, client, authHeaders):
        response = client.delete("/api/v1/iteration/99999", headers=authHeaders)
        assert response.status_code == 404


class TestFinalizeIterationAPI:

    def test_finalize_wrong_status(self, client, authHeaders, db, testProject):
        iteration = iteration_crud.create_iteration(db=db, project_id=testProject.id, name="定稿测试")
        response = client.post(
            f"/api/v1/iteration/{iteration.id}/finalize",
            headers=authHeaders,
        )
        assert response.status_code == 400

    def test_finalize_nonexistent(self, client, authHeaders):
        response = client.post("/api/v1/iteration/99999/finalize", headers=authHeaders)
        assert response.status_code == 404
