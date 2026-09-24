"""Phase 3 Task 4: SAML 2.0 SSO SP 端点单元测试。

覆盖 /api/v1/auth/saml/* 端点：
    - GET  /auth/saml/providers  : 列出 IdP（启用 / 禁用 503）
    - GET  /auth/saml/metadata   : SP 元数据 XML（成功 / 未知 IdP 404 / 禁用 503）
    - GET  /auth/saml/login      : 跳转 IdP SSO 页（302 / 未知 IdP 400 / 禁用 503）
    - POST /auth/saml/acs        : ACS 回调（成功 / RelayState 失败 400 / SAMLResponse 失败 401 /
                                   用户未绑定 403 / 禁用 503）
    - GET  /auth/saml/slo        : SLO 回调（成功 / 失败 / 禁用 503）

测试策略：
    - 禁用模式：所有端点返回 503
    - 启用模式：/providers / /metadata / /login 测试真实 python3-saml 流程（不 mock）
    - /acs / /slo 通过 mock SAMLService 方法验证端点契约与异常处理
    - 不依赖真实 IdP，全部通过 mock service 验证端点契约
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# R4-4：python3-saml（onelogin）未安装时整文件 skip，而非 fail —— 属环境依赖缺失，非代码缺陷
pytest.importorskip(
    "onelogin.saml2", reason="环境未安装 python3-saml(onelogin)，非代码缺陷"
)

from app.core.config import settings
from app.services.saml._settings_builder import (
    NAMEID_FORMAT_EMAIL,
    NAMEID_FORMAT_PERSISTENT,
)


# ── 测试用 IdP / SP 配置 ──

_TEST_SP_ENTITY_ID = "https://app.test.local/api/v1/auth/saml/metadata"
_TEST_SP_ACS_URL = "https://app.test.local/api/v1/auth/saml/acs"
_TEST_SP_SLO_URL = "https://app.test.local/api/v1/auth/saml/slo"

_TEST_IDP_CONFIGS = [
    {
        "provider": "okta",
        "entity_id": "http://www.okta.com/exk1234567890",
        "sso_url": "https://test.okta.com/app/test/exk1234567890/sso/saml",
        "slo_url": "https://test.okta.com/app/test/exk1234567890/slo/saml",
        "x509_cert": "MIIDpDCCAoygAwIBAgIGAX",
        "nameid_format": NAMEID_FORMAT_EMAIL,
        "sign_authn_request": False,
        "want_assertions_signed": True,
    },
    {
        "provider": "azure",
        "entity_id": "https://login.microsoftonline.com/tenant-id/",
        "sso_url": "https://login.microsoftonline.com/tenant-id/saml2",
        "slo_url": "https://login.microsoftonline.com/tenant-id/saml2/logout",
        "x509_cert": "MIIDpDCCAoygAwIBBgIGAX",
        "nameid_format": NAMEID_FORMAT_PERSISTENT,
    },
]


@pytest.fixture
def saml_enabled(monkeypatch):
    """启用 SAML 并配置测试 IdP 与 SP。"""
    monkeypatch.setattr(settings, "SAML_SSO_ENABLED", True)
    monkeypatch.setattr(settings, "SAML_IDP_CONFIGS", json.dumps(_TEST_IDP_CONFIGS))
    monkeypatch.setattr(settings, "SAML_DEFAULT_PROVIDER", "okta")
    monkeypatch.setattr(settings, "SAML_SP_ENTITY_ID", _TEST_SP_ENTITY_ID)
    monkeypatch.setattr(settings, "SAML_SP_ACS_URL", _TEST_SP_ACS_URL)
    monkeypatch.setattr(settings, "SAML_SP_SLO_URL", _TEST_SP_SLO_URL)
    monkeypatch.setattr(settings, "SAML_SP_X509_CERT", "")
    monkeypatch.setattr(settings, "SAML_SP_PRIVATE_KEY", "")
    # 清空 RelayState 内存存储，避免跨测试污染
    from app.services.saml._relay_state import _memory_relay_store
    _memory_relay_store.clear()
    yield
    _memory_relay_store.clear()


# ── 禁用模式测试 ──


class TestSAMLDisabled:
    """SAML_SSO_ENABLED=False 时所有端点返回 503。"""

    @pytest.mark.asyncio
    async def test_providers_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /providers 返回 503。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/saml/providers")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_metadata_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /metadata 返回 503。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/saml/metadata")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_login_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /login 返回 503。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/saml/login")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_acs_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /acs 返回 503。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", False)
        resp = await async_client.post(
            "/api/v1/auth/saml/acs",
            data={"SAMLResponse": "fake-response", "RelayState": "fake-relay"},
        )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_slo_returns_503_when_disabled(
        self, async_client: AsyncClient, monkeypatch
    ) -> None:
        """禁用时 /slo 返回 503。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", False)
        resp = await async_client.get("/api/v1/auth/saml/slo")
        assert resp.status_code == 503


# ── /providers 端点测试 ──


class TestListProvidersEndpoint:
    """GET /auth/saml/providers 端点测试。"""

    @pytest.mark.asyncio
    async def test_list_providers_success(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """启用时返回 IdP 列表。"""
        resp = await async_client.get("/api/v1/auth/saml/providers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert "providers" in data
        assert len(data["providers"]) == 2
        provider_names = [p["provider"] for p in data["providers"]]
        assert "okta" in provider_names
        assert "azure" in provider_names
        assert data["default_provider"] == "okta"


# ── /metadata 端点测试 ──


class TestMetadataEndpoint:
    """GET /auth/saml/metadata 端点测试。"""

    @pytest.mark.asyncio
    async def test_get_metadata_returns_xml(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """返回 SP 元数据 XML（application/xml）。"""
        resp = await async_client.get("/api/v1/auth/saml/metadata")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/xml")
        xml = resp.text
        # python3-saml 生成的元数据含 EntityDescriptor
        assert "EntityDescriptor" in xml
        assert _TEST_SP_ENTITY_ID in xml
        assert _TEST_SP_ACS_URL in xml

    @pytest.mark.asyncio
    async def test_get_metadata_with_provider(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """指定 provider 返回对应 SP 元数据 XML。"""
        resp = await async_client.get(
            "/api/v1/auth/saml/metadata", params={"provider": "okta"}
        )
        assert resp.status_code == 200
        assert "EntityDescriptor" in resp.text

    @pytest.mark.asyncio
    async def test_get_metadata_unknown_provider_returns_404(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """未知 provider 返回 404。"""
        resp = await async_client.get(
            "/api/v1/auth/saml/metadata", params={"provider": "unknown"}
        )
        assert resp.status_code == 404


# ── /login 端点测试 ──


class TestLoginEndpoint:
    """GET /auth/saml/login 端点测试。"""

    @pytest.mark.asyncio
    async def test_login_redirects_to_idp(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """login 端点 302 重定向到 IdP SSO URL。"""
        resp = await async_client.get("/api/v1/auth/saml/login")
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        # 重定向到 okta SSO URL，含 SAMLRequest 与 RelayState 参数
        assert location.startswith("https://test.okta.com/app/test/exk1234567890/sso/saml")
        assert "SAMLRequest=" in location
        assert "RelayState=" in location

    @pytest.mark.asyncio
    async def test_login_with_custom_provider(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """指定 provider=azure 时重定向到 Azure AD SSO URL。"""
        resp = await async_client.get(
            "/api/v1/auth/saml/login", params={"provider": "azure"}
        )
        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert location.startswith(
            "https://login.microsoftonline.com/tenant-id/saml2"
        )
        assert "SAMLRequest=" in location

    @pytest.mark.asyncio
    async def test_login_with_unknown_provider_returns_400(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """未知 provider 返回 400。"""
        resp = await async_client.get(
            "/api/v1/auth/saml/login", params={"provider": "unknown"}
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_login_with_redirect_to(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """redirect_to 参数不影响 302 跳转（存入 RelayState 上下文）。"""
        resp = await async_client.get(
            "/api/v1/auth/saml/login", params={"redirect_to": "/dashboard"}
        )
        assert resp.status_code == 302
        assert "SAMLRequest=" in resp.headers.get("location", "")


# ── /acs 端点测试 ──


class TestACSEndpoint:
    """POST /auth/saml/acs 端点测试。"""

    @pytest.mark.asyncio
    async def test_acs_success(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """ACS 回调成功（mock handle_acs 返回 token + 用户信息）。"""
        mock_result = {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "token_type": "bearer",
            "user": {
                "id": 999,
                "username": "saml_testuser",
                "email": "saml@test.com",
                "saml_provider": "okta",
            },
        }
        with patch(
            "app.services.saml_service.SAMLService.handle_acs",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = await async_client.post(
                "/api/v1/auth/saml/acs",
                data={
                    "SAMLResponse": "base64-encoded-saml-response",
                    "RelayState": "some-relay-state",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["msg"] == "SAML 登录成功"
        data = body["data"]
        assert data["access_token"] == "mock-access-token"
        assert data["refresh_token"] == "mock-refresh-token"
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "saml_testuser"
        assert data["user"]["saml_provider"] == "okta"

    @pytest.mark.asyncio
    async def test_acs_relay_state_error_returns_400(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """RelayState 校验失败返回 400。"""
        from app.services.saml_service import SAMLRelayStateError

        with patch(
            "app.services.saml_service.SAMLService.handle_acs",
            new_callable=AsyncMock,
            side_effect=SAMLRelayStateError("RelayState 不存在"),
        ):
            resp = await async_client.post(
                "/api/v1/auth/saml/acs",
                data={
                    "SAMLResponse": "fake-response",
                    "RelayState": "invalid-relay",
                },
            )
        assert resp.status_code == 400
        assert "RelayState" in resp.json()["msg"]

    @pytest.mark.asyncio
    async def test_acs_response_error_returns_401(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """SAMLResponse 校验失败返回 401。"""
        from app.services.saml_service import SAMLResponseError

        with patch(
            "app.services.saml_service.SAMLService.handle_acs",
            new_callable=AsyncMock,
            side_effect=SAMLResponseError("SAMLResponse 签名失败"),
        ):
            resp = await async_client.post(
                "/api/v1/auth/saml/acs",
                data={
                    "SAMLResponse": "tampered-response",
                    "RelayState": "some-relay",
                },
            )
        assert resp.status_code == 401
        assert "SAMLResponse" in resp.json()["msg"]

    @pytest.mark.asyncio
    async def test_acs_user_not_bound_returns_403(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """用户未绑定且禁止自动注册返回 403。"""
        from app.services.saml_service import SAMLUserNotBoundError

        with patch(
            "app.services.saml_service.SAMLService.handle_acs",
            new_callable=AsyncMock,
            side_effect=SAMLUserNotBoundError(),
        ):
            resp = await async_client.post(
                "/api/v1/auth/saml/acs",
                data={
                    "SAMLResponse": "valid-response",
                    "RelayState": "some-relay",
                },
            )
        assert resp.status_code == 403
        assert "未绑定" in resp.json()["msg"]

    @pytest.mark.asyncio
    async def test_acs_config_error_returns_400(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """配置错误返回 400。"""
        from app.services.saml_service import SAMLConfigError

        with patch(
            "app.services.saml_service.SAMLService.handle_acs",
            new_callable=AsyncMock,
            side_effect=SAMLConfigError("IdP 配置缺失"),
        ):
            resp = await async_client.post(
                "/api/v1/auth/saml/acs",
                data={
                    "SAMLResponse": "response",
                    "RelayState": "relay",
                },
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_acs_service_error_returns_500(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """其他 SAMLServiceError 返回 500。"""
        from app.services.saml_service import SAMLServiceError

        with patch(
            "app.services.saml_service.SAMLService.handle_acs",
            new_callable=AsyncMock,
            side_effect=SAMLServiceError("内部错误", code=500),
        ):
            resp = await async_client.post(
                "/api/v1/auth/saml/acs",
                data={
                    "SAMLResponse": "response",
                    "RelayState": "relay",
                },
            )
        assert resp.status_code == 500


# ── /slo 端点测试 ──


class TestSLOEndpoint:
    """GET /auth/saml/slo 端点测试。"""

    @pytest.mark.asyncio
    async def test_slo_success(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """SLO 回调成功。"""
        with patch(
            "app.services.saml_service.SAMLService.handle_slo",
            return_value=(True, "SLO 成功"),
        ):
            resp = await async_client.get("/api/v1/auth/saml/slo")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["logged_out"] is True
        assert "SLO" in body["msg"]

    @pytest.mark.asyncio
    async def test_slo_failure_returns_200_with_error_code(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """SLO 校验失败返回 200 但业务码 400（IdP 返回无效 LogoutResponse）。"""
        with patch(
            "app.services.saml_service.SAMLService.handle_slo",
            return_value=(False, "LogoutResponse 校验失败"),
        ):
            resp = await async_client.get("/api/v1/auth/saml/slo")
        # 端点设计：失败时返回 create_response(code=400)，HTTP 状态仍为 200
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400
        assert body["data"]["logged_out"] is False
        assert "校验失败" in body["msg"]

    @pytest.mark.asyncio
    async def test_slo_config_error_returns_400(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """配置错误返回 400。"""
        from app.services.saml_service import SAMLConfigError

        with patch(
            "app.services.saml_service.SAMLService.handle_slo",
            side_effect=SAMLConfigError("未知 IdP"),
        ):
            resp = await async_client.get("/api/v1/auth/saml/slo")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_slo_service_error_returns_500(
        self, async_client: AsyncClient, saml_enabled
    ) -> None:
        """其他 SAMLServiceError 返回 500。"""
        from app.services.saml_service import SAMLServiceError

        with patch(
            "app.services.saml_service.SAMLService.handle_slo",
            side_effect=SAMLServiceError("内部错误", code=500),
        ):
            resp = await async_client.get("/api/v1/auth/saml/slo")
        assert resp.status_code == 500
