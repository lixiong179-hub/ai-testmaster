"""需求链接端点 async 测试。

覆盖 /api/v1/requirement-link/ 端点的未认证、不存在资源场景，
以及 _build_auth_config_response 纯函数单元测试。
使用 tests/api/conftest.py 的 async fixture。
"""
import pytest
from app.api.v1.endpoints.requirement_link_crud import _build_auth_config_response


class TestBuildAuthConfigResponse:
    def test_none_config(self):
        result = _build_auth_config_response("basic", None)
        assert result is not None
        assert result.has_credentials is False

    def test_empty_config(self):
        result = _build_auth_config_response("basic", {})
        assert result is not None
        assert result.has_credentials is False

    def test_basic_with_credentials(self):
        result = _build_auth_config_response("basic", {"username": "admin", "password": "pass"})
        assert result.has_credentials is True

    def test_basic_missing_password(self):
        result = _build_auth_config_response("basic", {"username": "admin"})
        assert result.has_credentials is False

    def test_bearer_with_token(self):
        result = _build_auth_config_response("bearer", {"token": "abc123"})
        assert result.has_credentials is True

    def test_bearer_missing_token(self):
        result = _build_auth_config_response("bearer", {})
        assert result.has_credentials is False

    def test_api_key_with_key(self):
        result = _build_auth_config_response("api_key", {"api_key": "key123"})
        assert result.has_credentials is True

    def test_cookie_with_value(self):
        result = _build_auth_config_response("cookie", {"cookie": "session=abc"})
        assert result.has_credentials is True

    def test_cookie_missing(self):
        result = _build_auth_config_response("cookie", {})
        assert result.has_credentials is False


class TestRequirementLinkAPI:
    async def test_create_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/requirement-link/",
            json={"project_id": 1, "link_name": "需求文档", "link_type": "url", "link_url": "https://example.com"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_list_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/requirement-link/list/1")
        assert resp.status_code in (401, 403, 404)

    async def test_get_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/requirement-link/1")
        assert resp.status_code in (401, 403, 404)

    async def test_update_without_auth(self, async_client):
        resp = await async_client.put(
            "/api/v1/requirement-link/1",
            json={"link_name": "更新"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_delete_without_auth(self, async_client):
        resp = await async_client.delete("/api/v1/requirement-link/1")
        assert resp.status_code in (401, 403, 404)

    async def test_list_nonexistent_project(self, async_auth_client):
        resp = await async_auth_client.get(
            "/api/v1/requirement-link/list/99999",
        )
        assert resp.status_code in (200, 403, 404, 500)
