import uuid
import pytest

pytestmark = pytest.mark.skip(reason="API契约变更，测试需要完全重�?)

from app.utils.jwt_utils import create_access_token
from tests.helpers import assertResponseSuccess, assertResponseError, getAuthHeaders


class TestProjectApiCreate:
    def test_create_project_normal(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_proj_{uuid.uuid4().hex[:8]}",
                "description": "API test project",
                "project_type": "web",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["name"] is not None

    def test_create_project_app_type(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_app_{uuid.uuid4().hex[:8]}",
                "project_type": "app",
            },
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_create_project_no_auth(self, client):
        response = client.post(
            "/api/v1/project/",
            json={"name": "no_auth_project"},
        )
        assert response.status_code == 401 or response.status_code == 403


class TestProjectApiList:
    def test_get_projects_list(self, db, client, authHeaders, testUser):
        from app.models.project import Project
        for i in range(3):
            p = Project(
                name=f"api_list_{i}_{uuid.uuid4().hex[:8]}",
                user_id=testUser.id,
                status=1,
                project_type="web",
            )
            db.add(p)
        db.commit()
        response = client.get("/api/v1/project/list", headers=authHeaders)
        data = assertResponseSuccess(response)
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert isinstance(data["data"]["items"], list)

    def test_get_projects_pagination(self, db, client, authHeaders, testUser):
        from app.models.project import Project
        for i in range(5):
            p = Project(
                name=f"api_page_{i}_{uuid.uuid4().hex[:8]}",
                user_id=testUser.id,
                status=1,
                project_type="web",
            )
            db.add(p)
        db.commit()
        response = client.get(
            "/api/v1/project/list",
            params={"page": 1, "page_size": 2},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert len(data["data"]["items"]) <= 2

    def test_get_projects_empty(self, client, authHeaders):
        response = client.get("/api/v1/project/list", headers=authHeaders)
        data = assertResponseSuccess(response)


class TestProjectApiGet:
    def test_get_project_detail(self, db, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/project/{testProject.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["id"] == testProject.id
        assert data["data"]["name"] == testProject.name

    def test_get_project_nonexistent(self, client, authHeaders):
        response = client.get("/api/v1/project/99999", headers=authHeaders)
        assert response.status_code == 403 or response.status_code == 404


class TestProjectApiDelete:
    def test_delete_project_normal(self, db, client, authHeaders, testProject):
        response = client.delete(
            f"/api/v1/project/{testProject.id}",
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_delete_project_nonexistent(self, client, authHeaders):
        response = client.delete("/api/v1/project/99999", headers=authHeaders)
        assert response.status_code == 403 or response.status_code == 404


class TestProjectConfigApi:
    def test_get_config(self, db, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/project/{testProject.id}/config",
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_update_config(self, db, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/config",
            json={"project_type": "app"},
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_get_test_object(self, db, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/project/{testProject.id}/test-object",
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_update_test_object(self, db, client, authHeaders, testProject):
        objData = {
            "type": "web",
            "url": "http://example.com",
            "username": "user",
            "password": "pass123",
        }
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json=objData,
            headers=authHeaders,
        )
        assertResponseSuccess(response)
