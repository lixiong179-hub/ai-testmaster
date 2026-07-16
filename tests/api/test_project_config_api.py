import pytest
from app.api.v1.endpoints.project_config import _parse_web_env_configs


class TestParseWebEnvConfigs:
    def test_none_configs(self):
        class FakeProject:
            web_env_configs = None
        result = _parse_web_env_configs(FakeProject())
        assert result is None

    def test_empty_configs(self):
        class FakeProject:
            web_env_configs = ""
        result = _parse_web_env_configs(FakeProject())
        assert result is None

    def test_valid_json(self):
        class FakeProject:
            web_env_configs = '{"test": {"url": "http://test.com", "password": "secret123"}}'
        result = _parse_web_env_configs(FakeProject())
        assert result is not None
        assert result["test"]["password"] != "secret123"

    def test_invalid_json(self):
        class FakeProject:
            web_env_configs = "not json"
        result = _parse_web_env_configs(FakeProject())
        assert result is None

    def test_multiple_envs(self):
        class FakeProject:
            web_env_configs = '{"test": {"password": "p1"}, "staging": {"password": "p2"}, "prod": {"password": "p3"}}'
        result = _parse_web_env_configs(FakeProject())
        assert result is not None
        assert result["test"]["password"] != "p1"
        assert result["staging"]["password"] != "p2"
        assert result["prod"]["password"] != "p3"

    def test_no_password_field(self):
        class FakeProject:
            web_env_configs = '{"test": {"url": "http://test.com"}}'
        result = _parse_web_env_configs(FakeProject())
        assert result is not None
        assert "password" not in result["test"]


class TestProjectConfigAPI:
    async def test_get_config_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/project/1/config")
        assert resp.status_code in (401, 403, 404)

    async def test_update_config_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/project/1/config",
            json={"web_env_configs": "{}"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_test_object_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/project/1/test-object")
        assert resp.status_code in (401, 403, 404)

    async def test_update_test_object_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/project/1/test-object",
            json={"app_name": "测试应用"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_get_config_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/project/99999/config",
        )
        assert resp.status_code in (403, 404, 500)

    async def test_get_test_object_nonexistent(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/project/99999/test-object",
        )
        assert resp.status_code in (403, 404, 500)
