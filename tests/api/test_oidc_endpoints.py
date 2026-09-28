"""Phase 3 Task 5: OIDC SSO 端点单元测试。

覆盖 /api/v1/auth/oidc/* 端点：
    - GET  /auth/oidc/providers  : 列出 IdP（启用 / 禁用 503）
    - GET  /auth/oidc/metadata   : 单个 IdP 元数据 / 不存在 404 / 全部列表
    - GET  /auth/oidc/login      : 跳转 IdP（302 / 400 / 503）
    - GET  /auth/oidc/callback   : 回调处理（错误响应 / 缺参数 400 / state 失败 / 成功）

测试策略：
    - 禁用模式：所有端点返回 503
    - 启用模式：mock OIDCService 验证端点路由与异常处理
    - 不依赖真实 IdP，全部通过 mock service 验证端点契约
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings


# ── 测试用 IdP 配置 ──

_TEST_IDP_CONFIGS = [
    {
        "provider": "google",
        "client_id": "google-client-id",
        "client_secret": "google-secret",
        "issuer": "https://accounts.google.com",
        "scopes": "openid email profile",
        "redirect_uri": "http://localhost:5173/api/v1/auth/oidc/callback",
    }
]


@pytest.fixture
def oidc_enabled(monkeypatch):
    """启用 OIDC 并配置测试 IdP。"""
    monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", True)
    monkeypatch.setattr(
        settings, "OIDC_IDP_CONFIGS", json.dumps(_TEST_IDP_CONFIGS)
    )
    monkeypatch.setattr(settings, "OIDC_DEFAULT_PROVIDER", "google")
    yield


# ── 禁用模式测试 ──


class TestOIDCDisabled:
    """OIDC_SSO_ENABLED=False 时所有端点返回 503。"""

    @pytest.mark.asyncio
    async def test_providers_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /providers 返回 503。"""
        monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/oidc/providers")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_metadata_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /metadata 返回 503。"""
        monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/oidc/metadata")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_login_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /login 返回 503。"""
        monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/oidc/login")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_callback_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /callback 返回 503。"""
        monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", False)
        resp = await async_client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "fake-code", "state": "fake-state"},
        )
        assert resp.status_code == 503


# ── /providers 端点测试 ──


class TestListProvidersEndpoint:
    """GET /auth/oidc/providers 端点测试。"""

    @pytest.mark.asyncio
    async def test_list_providers_success(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """启用时返回 IdP 列表。"""
        resp = await async_client.get("/api/v1/auth/oidc/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert "providers" in data
        assert len(data["providers"]) == 1
        assert data["providers"][0]["provider"] == "google"
        assert data["default_provider"] == "google"


# ── /metadata 端点测试 ──


class TestMetadataEndpoint:
    """GET /auth/oidc/metadata 端点测试。"""

    @pytest.mark.asyncio
    async def test_get_all_metadata(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """不传 provider 返回所有 IdP 列表。"""
        resp = await async_client.get("/api/v1/auth/oidc/metadata")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "providers" in data

    @pytest.mark.asyncio
    async def test_get_single_metadata(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """指定 provider 返回单个 IdP 元数据。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/metadata", params={"provider": "google"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["provider"] == "google"
        assert data["client_id"] == "google-client-id"
        # 脱敏：不返回 client_secret
        assert "client_secret" not in data

    @pytest.mark.asyncio
    async def test_get_metadata_unknown_provider(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """未知 provider 返回 404。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/metadata", params={"provider": "unknown"}
        )
        assert resp.status_code == 404


# ── /login 端点测试 ──


class TestLoginEndpoint:
    """GET /auth/oidc/login 端点测试。"""

    @pytest.mark.asyncio
    async def test_login_redirects_to_idp(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """login 端点 302 重定向到 IdP 授权 URL。"""
        # httpx AsyncClient 默认 follow_redirects=False，应返回 302
        resp = await async_client.get("/api/v1/auth/oidc/login")
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert location.startswith("https://accounts.google.com/authorize?")
        assert "response_type=code" in location
        assert "client_id=google-client-id" in location
        assert "state=" in location
        assert "nonce=" in location

    @pytest.mark.asyncio
    async def test_login_with_custom_provider(
        self, async_client: AsyncClient, oidc_enabled, monkeypatch
    ) -> None:
        """指定 provider 时使用对应 IdP 配置。"""
        # 添加 azure 配置
        configs = _TEST_IDP_CONFIGS + [
            {
                "provider": "azure",
                "client_id": "azure-id",
                "client_secret": "azure-secret",
                "issuer": "https://login.microsoftonline.com/tenant/v2.0",
                "scopes": "openid email profile",
                "redirect_uri": "http://localhost:5173/api/v1/auth/oidc/callback",
            }
        ]
        monkeypatch.setattr(settings, "OIDC_IDP_CONFIGS", json.dumps(configs))

        resp = await async_client.get(
            "/api/v1/auth/oidc/login", params={"provider": "azure"}
        )
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert location.startswith(
            "https://login.microsoftonline.com/tenant/v2.0/authorize?"
        )
        assert "client_id=azure-id" in location

    @pytest.mark.asyncio
    async def test_login_with_unknown_provider_returns_400(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """未知 provider 返回 400。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/login", params={"provider": "unknown"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_login_with_redirect_to(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """redirect_to 参数不影响 302 跳转（存入 state 上下文）。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/login", params={"redirect_to": "/dashboard"}
        )
        assert resp.status_code == 302


# ── /callback 端点测试 ──


class TestCallbackEndpoint:
    """GET /auth/oidc/callback 端点测试。"""

    @pytest.mark.asyncio
    async def test_callback_with_idp_error(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """IdP 返回 error 时返回 400 + 错误信息。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/callback",
            params={
                "error": "access_denied",
                "error_description": "User denied consent",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400
        assert "access_denied" in body["msg"]
        assert body["data"]["error"] == "access_denied"

    @pytest.mark.asyncio
    async def test_callback_missing_code_returns_400(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """缺少 code 参数返回 400。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/callback", params={"state": "some-state"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_missing_state_returns_400(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """缺少 state 参数返回 400。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/callback", params={"code": "some-code"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_with_invalid_state_returns_400(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """无效 state 返回 400（state 不存在或已过期）。"""
        resp = await async_client.get(
            "/api/v1/auth/oidc/callback",
            params={"code": "fake-code", "state": "invalid-state"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_success(
        self, async_client: AsyncClient, oidc_enabled
    ) -> None:
        """完整回调流程成功（mock service 验证端点契约）。"""
        # 1. 先调用 /login 获取有效 state（state 存入内存 store）
        login_resp = await async_client.get("/api/v1/auth/oidc/login")
        assert login_resp.status_code == 302
        location = login_resp.headers.get("location", "")
        # 从 location URL 中提取 state 参数
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        state = params["state"][0]

        # 2. mock handle_callback 返回成功结果
        mock_result = {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "bearer",
            "user": {
                "id": 999,
                "username": "sso_testuser",
                "email": "sso@test.com",
                "oidc_provider": "google",
            },
        }

        # 直接 patch OIDCService.handle_callback 为 AsyncMock
        with patch(
            "app.services.oidc_service.OIDCService.handle_callback",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            # 需要先消费 state（mock 后 state 不会被消费，需手动处理）
            # 但 mock 后整个 handle_callback 不执行，state 不会被消费
            # 实际上 exchange_code_for_tokens 会先消费 state
            # 所以也要 mock exchange_code_for_tokens
            with patch(
                "app.services.oidc_service.OIDCService.exchange_code_for_tokens",
                new_callable=AsyncMock,
                return_value={"id_token": "mock-id-token", "access_token": "mock-idp-token"},
            ):
                # parse_id_token 也需 mock（避免实际 JWT 解析）
                with patch(
                    "app.services.oidc_service.OIDCService.parse_id_token",
                    return_value={
                        "sub": "test-sub",
                        "email": "sso@test.com",
                        "iss": "https://accounts.google.com",
                        "aud": "google-client-id",
                        "exp": 9999999999,
                        "iat": 1111111111,
                    },
                ):
                    # provision_user 也需 mock
                    mock_user = MagicMock()
                    mock_user.id = 999
                    mock_user.username = "sso_testuser"
                    mock_user.email = "sso@test.com"
                    mock_user.login_count = 0
                    with patch(
                        "app.services.oidc_service.OIDCService.provision_user",
                        new_callable=AsyncMock,
                        return_value=mock_user,
                    ):
                        # session_service.create_session 也需 mock
                        with patch(
                            "app.services.session_service.SessionService.create_session",
                            new_callable=AsyncMock,
                        ):
                            # create_access_token / create_refresh_token_with_jti 也需 mock
                            # （拆分后位于 oidc_user_mixin，而非 oidc_service）
                            with patch(
                                "app.services.oidc_user_mixin.create_access_token",
                                return_value="mock-access-token",
                            ):
                                with patch(
                                    "app.services.oidc_user_mixin.create_refresh_token_with_jti",
                                    return_value=("mock-refresh-token", "mock-jti"),
                                ):
                                    resp = await async_client.get(
                                        "/api/v1/auth/oidc/callback",
                                        params={
                                            "code": "test-code",
                                            "state": state,
                                        },
                                    )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["msg"] == "OIDC 登录成功"
        data = body["data"]
        assert data["access_token"] == "mock-access-token"
        assert data["refresh_token"] == "mock-refresh-token"
        assert data["user"]["username"] == "sso_testuser"
        assert data["user"]["oidc_provider"] == "google"
