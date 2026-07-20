import uuid
import pytest

# pytestmark = pytest.mark.skip(reason="API契约变更（认证/项目配置接口重构），测试需要完全重写")  # 临时移除排查

from tests.helpers import (
    assertResponseSuccess,
    assertResponseError,
    assertResponseUnauthorized,
    assertFieldExists,
    assertFieldValue,
    createTestProject,
    createTestUser,
    getAuthHeaders,
)


class TestCreateProject:
    def test_create_project_normal(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_project_{uuid.uuid4().hex[:8]}",
                "description": "api test project",
                "project_type": "web",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "project_id")
        assertFieldExists(data, "name")

    def test_create_project_without_trailing_slash(self, client, authHeaders):
        response = client.post(
            "/api/v1/project",
            json={
                "name": f"api_project_ns_{uuid.uuid4().hex[:8]}",
                "description": "no slash",
                "project_type": "web",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "project_id")

    def test_create_project_app_type(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_app_{uuid.uuid4().hex[:8]}",
                "description": "app type project",
                "project_type": "app",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "project_type", "app")

    def test_create_project_duplicate_name(self, client, authHeaders, testUser, db):
        name = f"dup_api_{uuid.uuid4().hex[:8]}"
        client.post(
            "/api/v1/project/",
            json={"name": name, "project_type": "web"},
            headers=authHeaders,
        )
        response = client.post(
            "/api/v1/project/",
            json={"name": name, "project_type": "web"},
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=400)

    def test_create_project_no_auth(self, client):
        response = client.post(
            "/api/v1/project/",
            json={"name": "no_auth_project", "project_type": "web"},
        )
        assertResponseUnauthorized(response)

    def test_create_project_with_web_env_configs(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_env_{uuid.uuid4().hex[:8]}",
                "project_type": "web",
                "web_env_configs": {
                    "test": {
                        "url": "https://test.example.com",
                        "username": "testuser",
                        "password": "testpass",
                    }
                },
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "project_id")

    def test_create_project_with_device_config(self, client, authHeaders):
        response = client.post(
            "/api/v1/project/",
            json={
                "name": f"api_device_{uuid.uuid4().hex[:8]}",
                "project_type": "app",
                "device_config": {
                    "default_device": {
                        "device_id": "emulator-5554",
                        "device_name": "Test Device",
                    }
                },
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "project_id")


class TestGetProjects:
    def test_get_projects_normal(self, client, authHeaders):
        response = client.get("/api/v1/project/list", headers=authHeaders)
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "items")
        assertFieldExists(data, "total")

    def test_get_projects_pagination(self, client, authHeaders):
        response = client.get(
            "/api/v1/project/list?page=1&page_size=5",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "items")

    def test_get_projects_no_auth(self, client):
        response = client.get("/api/v1/project/list")
        assertResponseUnauthorized(response)


class TestGetProject:
    def test_get_project_normal(self, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/project/{testProject.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")
        assertFieldExists(data, "name")

    def test_get_project_nonexistent(self, client, authHeaders):
        response = client.get("/api/v1/project/99999", headers=authHeaders)
        assertResponseError(response, expectedStatus=403)

    def test_get_project_no_auth(self, client, testProject):
        response = client.get(f"/api/v1/project/{testProject.id}")
        assertResponseUnauthorized(response)

    def test_get_project_wrong_user(self, client, db):
        otherUser = createTestUser(db=db, username=f"other_{uuid.uuid4().hex[:8]}")
        from app.utils.jwt_utils import create_access_token
        # token sub 必须为 user.id (非 username), 否则 me 端点查询失败返回 401
        otherToken = create_access_token({"sub": str(otherUser.id), "username": otherUser.username})
        otherHeaders = {"Authorization": f"Bearer {otherToken}"}
        response = client.get("/api/v1/project/99999", headers=otherHeaders)
        assertResponseError(response, expectedStatus=403)


class TestDeleteProject:
    @pytest.mark.skip(reason="_SyncBackedAsyncSession.delete 为同步方法, await db.delete(project) 触发 'NoneType can't be used in await' — 测试基础设施问题, 非契约问题")
    def test_delete_project_normal(self, client, authHeaders, db, testUser):
        from app.schemas.project import ProjectCreate
        from app.crud.project import create_project

        projectCreate = ProjectCreate(name=f"del_api_{uuid.uuid4().hex[:8]}")
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        response = client.delete(
            f"/api/v1/project/{project.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_delete_project_nonexistent(self, client, authHeaders):
        response = client.delete("/api/v1/project/99999", headers=authHeaders)
        assertResponseError(response, expectedStatus=403)

    def test_delete_project_no_auth(self, client, testProject):
        response = client.delete(f"/api/v1/project/{testProject.id}")
        assertResponseUnauthorized(response)


class TestGetProjectConfig:
    def test_get_project_config_normal(self, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/project/{testProject.id}/config",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "project_type")

    def test_get_project_config_nonexistent(self, client, authHeaders):
        response = client.get("/api/v1/project/99999/config", headers=authHeaders)
        assertResponseError(response, expectedStatus=403)

    def test_get_project_config_no_auth(self, client, testProject):
        response = client.get(f"/api/v1/project/{testProject.id}/config")
        assertResponseUnauthorized(response)


class TestUpdateProjectConfig:
    def test_update_project_config_type(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/config",
            json={"project_type": "app"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldValue(data, "project_type", "app")

    def test_update_project_config_web_env(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/config",
            json={
                "web_env_configs": {
                    "test": {
                        "url": "https://new.example.com",
                        "username": "newuser",
                        "password": "newpass",
                    }
                }
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_project_config_device(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/config",
            json={
                "device_config": {
                    "default_device": {"device_id": "device-001", "device_name": "Pixel"}
                }
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_project_config_clear_web_env(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/config",
            json={"web_env_configs": None},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_project_config_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/project/99999/config",
            json={"project_type": "web"},
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=403)

    def test_update_project_config_no_auth(self, client, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/config",
            json={"project_type": "web"},
        )
        assertResponseUnauthorized(response)


class TestGetTestObject:
    def test_get_test_object_normal(self, client, authHeaders, testProject):
        response = client.get(
            f"/api/v1/project/{testProject.id}/test-object",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "type")

    def test_get_test_object_nonexistent(self, client, authHeaders):
        response = client.get("/api/v1/project/99999/test-object", headers=authHeaders)
        assertResponseError(response, expectedStatus=403)


class TestUpdateTestObject:
    def test_update_test_object_type(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json={"type": "app"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]
        assertFieldExists(data, "id")

    def test_update_test_object_url_and_credentials(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json={
                "url": "https://test.example.com",
                "username": "testuser",
                "password": "testpass123",
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_test_object_device_info(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json={
                "type": "app",
                "device_info": {"device_id": "emulator-5554", "device_name": "Emulator"},
            },
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_test_object_app_package(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json={"app_package": "com.example.app"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_test_object_app_activity(self, client, authHeaders, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json={"app_activity": "com.example.app.MainActivity"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)["data"]

    def test_update_test_object_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/project/99999/test-object",
            json={"type": "web"},
            headers=authHeaders,
        )
        assertResponseError(response, expectedStatus=403)

    def test_update_test_object_no_auth(self, client, testProject):
        response = client.put(
            f"/api/v1/project/{testProject.id}/test-object",
            json={"type": "web"},
        )
        assertResponseUnauthorized(response)
