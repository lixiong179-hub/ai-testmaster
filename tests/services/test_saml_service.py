"""Phase 3 Task 4: SAML 2.0 SSO SP 服务单元测试。

覆盖：
    - SAMLService 初始化: 禁用模式 / 未配置 IdP / SP 配置不完整 / 启用模式
    - IdP 配置管理: list_providers / get_provider_config / resolve_provider
    - RelayState 管理: 生成 / 存储 / 消费 / 过期 / 一次性 / 空 value
    - Settings 构建: PEM 规范化 / SP 配置 / IdP 配置 / 完整配置 / security 配置
    - 用户配置: 按 (issuer,nameid) 查找 / 按 email 绑定 / 自动创建 / 禁止自动注册
    - 邮箱提取: 标准属性 / OASIS 属性 / NameID 回退
    - 用户名生成: 各种来源 / 非法字符清理 / 唯一后缀
    - 元数据: 单个 IdP / 列表 / 默认 IdP
    - 请求上下文: 最小占位 / 从 Request 构建
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

# R4-4：python3-saml（onelogin）未安装时整文件 skip，而非 fail —— 属环境依赖缺失，非代码缺陷
pytest.importorskip(
    "onelogin.saml2", reason="环境未安装 python3-saml(onelogin)，非代码缺陷"
)

from app.core.config import settings
from app.services.saml._relay_state import RelayStateStore, _memory_relay_store
from app.services.saml._settings_builder import (
    DEFAULT_NAMEID_FORMAT,
    NAMEID_FORMAT_EMAIL,
    NAMEID_FORMAT_PERSISTENT,
    _normalize_pem,
    build_full_settings_dict,
    build_idp_settings_dict,
    build_sp_settings_dict,
)
from app.services.saml._user_provisioning import SAMLUserProvisioner
from app.services.saml_service import (
    SAMLConfigError,
    SAMLDisabledError,
    SAMLService,
    SAMLUserNotBoundError,
    get_saml_service,
)


# ── 测试用 IdP 配置 ──

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
    _memory_relay_store.clear()
    yield
    _memory_relay_store.clear()


@pytest.fixture
def saml_service(saml_enabled) -> SAMLService:
    """创建 SAMLService 实例（已启用）。"""
    return SAMLService()


@pytest.fixture
def relay_store() -> RelayStateStore:
    """创建 RelayStateStore 实例。"""
    _memory_relay_store.clear()
    store = RelayStateStore()
    yield store
    _memory_relay_store.clear()


@pytest.fixture
def provisioner() -> SAMLUserProvisioner:
    """创建 SAMLUserProvisioner 实例。"""
    return SAMLUserProvisioner()


# ── 初始化测试 ──


class TestSAMLServiceInit:
    """SAMLService 初始化测试。"""

    def test_init_raises_when_disabled(self, monkeypatch) -> None:
        """SAML_SSO_ENABLED=False 时抛出 SAMLDisabledError。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", False)
        with pytest.raises(SAMLDisabledError):
            SAMLService()

    def test_init_raises_when_no_idp_configured(self, monkeypatch) -> None:
        """SAML_IDP_CONFIGS 为空时抛出 SAMLConfigError。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", True)
        monkeypatch.setattr(settings, "SAML_IDP_CONFIGS", "[]")
        monkeypatch.setattr(settings, "SAML_SP_ENTITY_ID", _TEST_SP_ENTITY_ID)
        monkeypatch.setattr(settings, "SAML_SP_ACS_URL", _TEST_SP_ACS_URL)
        with pytest.raises(SAMLConfigError, match="未配置任何 SAML IdP"):
            SAMLService()

    def test_init_raises_when_sp_entity_id_missing(self, monkeypatch) -> None:
        """SAML_SP_ENTITY_ID 为空时抛出 SAMLConfigError。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", True)
        monkeypatch.setattr(settings, "SAML_IDP_CONFIGS", json.dumps(_TEST_IDP_CONFIGS))
        monkeypatch.setattr(settings, "SAML_SP_ENTITY_ID", "")
        monkeypatch.setattr(settings, "SAML_SP_ACS_URL", _TEST_SP_ACS_URL)
        with pytest.raises(SAMLConfigError, match="SP 配置不完整"):
            SAMLService()

    def test_init_raises_when_sp_acs_url_missing(self, monkeypatch) -> None:
        """SAML_SP_ACS_URL 为空时抛出 SAMLConfigError。"""
        monkeypatch.setattr(settings, "SAML_SSO_ENABLED", True)
        monkeypatch.setattr(settings, "SAML_IDP_CONFIGS", json.dumps(_TEST_IDP_CONFIGS))
        monkeypatch.setattr(settings, "SAML_SP_ENTITY_ID", _TEST_SP_ENTITY_ID)
        monkeypatch.setattr(settings, "SAML_SP_ACS_URL", "")
        with pytest.raises(SAMLConfigError, match="SP 配置不完整"):
            SAMLService()

    def test_get_saml_service_factory_returns_instance(self, saml_enabled) -> None:
        """get_saml_service 工厂函数返回实例。"""
        service = get_saml_service()
        assert isinstance(service, SAMLService)


# ── IdP 配置管理测试 ──


class TestProviderConfig:
    """IdP 配置管理测试。"""

    def test_list_providers(self, saml_service: SAMLService) -> None:
        """list_providers 返回所有配置的 IdP 标识。"""
        assert saml_service.list_providers() == ["okta", "azure"]

    def test_get_provider_config_existing(self, saml_service: SAMLService) -> None:
        """get_provider_config 返回指定 IdP 配置。"""
        cfg = saml_service.get_provider_config("okta")
        assert cfg["provider"] == "okta"
        assert cfg["entity_id"] == "http://www.okta.com/exk1234567890"

    def test_get_provider_config_default(self, saml_service: SAMLService) -> None:
        """provider=None 时返回默认 IdP 配置。"""
        cfg = saml_service.get_provider_config(None)
        assert cfg["provider"] == "okta"

    def test_get_provider_config_not_found(self, saml_service: SAMLService) -> None:
        """未配置的 IdP 抛出 SAMLConfigError。"""
        with pytest.raises(SAMLConfigError, match="未找到 IdP 配置"):
            saml_service.get_provider_config("nonexistent")

    def test_resolve_provider_with_value(self, saml_service: SAMLService) -> None:
        """resolve_provider 透传非 None 值。"""
        assert saml_service.resolve_provider("azure") == "azure"

    def test_resolve_provider_none_uses_default(
        self, saml_service: SAMLService
    ) -> None:
        """resolve_provider(None) 返回默认 IdP。"""
        assert saml_service.resolve_provider(None) == "okta"


# ── RelayState 管理测试 ──


class TestRelayStateStore:
    """RelayState 存储管理测试。"""

    def test_generate_unique(self, relay_store: RelayStateStore) -> None:
        """生成的 RelayState 唯一且足够长。"""
        states = {relay_store.generate() for _ in range(20)}
        assert len(states) == 20
        for s in states:
            assert len(s) >= 32

    def test_save_and_consume(self, relay_store: RelayStateStore) -> None:
        """存储后消费返回 payload。"""
        relay_store.save("relay-1", "okta", "/dashboard")
        payload = relay_store.consume("relay-1")
        assert payload is not None
        assert payload["provider"] == "okta"
        assert payload["redirect_to"] == "/dashboard"
        assert "expires_at" in payload

    def test_consume_one_time(self, relay_store: RelayStateStore) -> None:
        """RelayState 只能消费一次（防重放）。"""
        relay_store.save("relay-2", "okta")
        first = relay_store.consume("relay-2")
        second = relay_store.consume("relay-2")
        assert first is not None
        assert second is None

    def test_consume_nonexistent(self, relay_store: RelayStateStore) -> None:
        """消费不存在的 RelayState 返回 None。"""
        assert relay_store.consume("nonexistent") is None

    def test_consume_empty(self, relay_store: RelayStateStore) -> None:
        """消费空 RelayState 返回 None。"""
        assert relay_store.consume("") is None

    def test_consume_expired(self, relay_store: RelayStateStore, monkeypatch) -> None:
        """过期的 RelayState 返回 None。"""
        # 强制使用内存存储（避免 Redis 路径导致内存条目不存在）
        monkeypatch.setattr(
            "app.services.saml._relay_state._get_redis_client", lambda: None
        )
        relay_store.save("relay-expired", "okta")
        # 篡改过期时间为过去
        _memory_relay_store["relay-expired"]["expires_at"] = time.time() - 1
        assert relay_store.consume("relay-expired") is None

    def test_save_without_redirect_to(self, relay_store: RelayStateStore) -> None:
        """redirect_to 为 None 时存储空字符串。"""
        relay_store.save("relay-3", "okta", None)
        payload = relay_store.consume("relay-3")
        assert payload is not None
        assert payload["redirect_to"] == ""


# ── Settings 构建测试 ──


class TestSettingsBuilder:
    """python3-saml Settings 字典构建测试。"""

    def test_normalize_pem_with_marker(self) -> None:
        """含 BEGIN/END 标记的 PEM 原样返回。"""
        pem = "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----"
        assert _normalize_pem(pem, is_cert=True) == pem

    def test_normalize_pem_without_marker_cert(self) -> None:
        """纯 base64 证书补齐 PEM 标记。"""
        raw = "MIIDpDCCAoygAwIBAgIGAX"
        result = _normalize_pem(raw, is_cert=True)
        assert "BEGIN CERTIFICATE" in result
        assert raw in result

    def test_normalize_pem_without_marker_key(self) -> None:
        """纯 base64 私钥补齐 PRIVATE KEY 标记。"""
        raw = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwgg"
        result = _normalize_pem(raw, is_cert=False)
        assert "BEGIN PRIVATE KEY" in result
        assert raw in result

    def test_normalize_pem_empty(self) -> None:
        """空内容返回空字符串。"""
        assert _normalize_pem("", is_cert=True) == ""
        assert _normalize_pem("   ", is_cert=True) == ""

    def test_build_sp_settings_dict(self, saml_enabled) -> None:
        """SP Settings 字典包含必要字段。"""
        sp = build_sp_settings_dict()
        assert sp["entityId"] == _TEST_SP_ENTITY_ID
        assert sp["assertionConsumerService"]["url"] == _TEST_SP_ACS_URL
        assert sp["singleLogoutService"]["url"] == _TEST_SP_SLO_URL
        assert "x509cert" in sp
        assert "privateKey" in sp

    def test_build_idp_settings_dict(self) -> None:
        """IdP Settings 字典包含必要字段。"""
        idp_cfg = _TEST_IDP_CONFIGS[0]
        idp = build_idp_settings_dict(idp_cfg)
        assert idp["entityId"] == idp_cfg["entity_id"]
        assert idp["singleSignOnService"]["url"] == idp_cfg["sso_url"]
        assert idp["singleLogoutService"]["url"] == idp_cfg["slo_url"]
        assert idp["NameIDFormat"] == NAMEID_FORMAT_EMAIL

    def test_build_idp_settings_default_nameid_format(self) -> None:
        """未配置 nameid_format 时使用默认值。"""
        idp = build_idp_settings_dict({"provider": "test", "entity_id": "x", "sso_url": "y"})
        assert idp["NameIDFormat"] == DEFAULT_NAMEID_FORMAT

    def test_build_full_settings_dict(self, saml_enabled) -> None:
        """完整 Settings 字典包含 sp/idp/security。"""
        idp_cfg = _TEST_IDP_CONFIGS[0]
        full = build_full_settings_dict(idp_cfg, strict=True)
        assert full["strict"] is True
        assert "sp" in full
        assert "idp" in full
        assert "security" in full
        assert full["security"]["wantAssertionsSigned"] is True
        assert full["security"]["authnRequestsSigned"] is False

    def test_build_full_settings_dict_strict_false(self, saml_enabled) -> None:
        """strict=False 时关闭严格模式。"""
        idp_cfg = _TEST_IDP_CONFIGS[0]
        full = build_full_settings_dict(idp_cfg, strict=False)
        assert full["strict"] is False


# ── 用户配置测试 ──


class TestUserProvisioning:
    """SAML 用户配置（provisioning）测试。"""

    @pytest.mark.asyncio
    async def test_find_by_saml_returns_user(
        self, provisioner: SAMLUserProvisioner, sync_backed_async_db
    ) -> None:
        """按 (issuer, nameid) 查找已绑定用户。"""
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        user = User(
            username="saml_existing_user",
            email="saml_existing@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            saml_issuer="https://idp.test.local",
            saml_nameid="nameid-123",
        )
        sync_backed_async_db.add(user)
        await sync_backed_async_db.flush()

        found = await provisioner.find_by_saml(
            sync_backed_async_db, "https://idp.test.local", "nameid-123"
        )
        assert found is not None
        assert found.id == user.id

    @pytest.mark.asyncio
    async def test_find_by_saml_not_found(
        self, provisioner: SAMLUserProvisioner, sync_backed_async_db
    ) -> None:
        """未绑定的用户返回 None。"""
        found = await provisioner.find_by_saml(
            sync_backed_async_db, "https://idp.test.local", "nonexistent"
        )
        assert found is None

    @pytest.mark.asyncio
    async def test_provision_creates_new_user(
        self, provisioner: SAMLUserProvisioner, sync_backed_async_db, monkeypatch
    ) -> None:
        """自动配置创建新用户。"""
        monkeypatch.setattr(settings, "SAML_AUTO_PROVISION", True)
        attributes = {"email": "new_saml@test.com", "displayname": "New SAML User"}
        user = await provisioner.provision(
            sync_backed_async_db,
            "okta",
            "https://idp.test.local",
            f"nameid-new-{int(time.time())}",
            attributes,
        )
        assert user.saml_issuer == "https://idp.test.local"
        assert user.saml_provider == "okta"
        assert user.username.startswith(settings.SAML_USERNAME_PREFIX)
        assert user.email == "new_saml@test.com"
        assert user.is_active is True
        assert user.is_superuser is False

    @pytest.mark.asyncio
    async def test_provision_binds_existing_by_email(
        self, provisioner: SAMLUserProvisioner, sync_backed_async_db, monkeypatch
    ) -> None:
        """按 email 绑定已存在的本地账号。"""
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        monkeypatch.setattr(settings, "SAML_AUTO_PROVISION", True)
        suffix = str(int(time.time()))
        local_user = User(
            username=f"local_user_{suffix}",
            email=f"bind_test_{suffix}@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        sync_backed_async_db.add(local_user)
        await sync_backed_async_db.flush()

        attributes = {"email": f"bind_test_{suffix}@test.com"}
        user = await provisioner.provision(
            sync_backed_async_db,
            "okta",
            "https://idp.test.local",
            f"nameid-bind-{suffix}",
            attributes,
        )
        assert user.id == local_user.id
        assert user.saml_nameid == f"nameid-bind-{suffix}"
        assert user.saml_issuer == "https://idp.test.local"

    @pytest.mark.asyncio
    async def test_provision_raises_when_auto_provision_disabled(
        self, provisioner: SAMLUserProvisioner, sync_backed_async_db, monkeypatch
    ) -> None:
        """SAML_AUTO_PROVISION=False 时抛出 ValueError。"""
        monkeypatch.setattr(settings, "SAML_AUTO_PROVISION", False)
        with pytest.raises(ValueError, match="未绑定"):
            await provisioner.provision(
                sync_backed_async_db,
                "okta",
                "https://idp.test.local",
                f"nameid-np-{int(time.time())}",
                {},
            )


# ── 邮箱提取测试 ──


class TestExtractEmail:
    """SAML 属性邮箱提取测试。"""

    def test_extract_email_standard_key(self, provisioner: SAMLUserProvisioner) -> None:
        """标准 email 属性。"""
        attrs = {"email": "user@test.com"}
        assert provisioner._extract_email(attrs, "") == "user@test.com"

    def test_extract_email_mail_key(self, provisioner: SAMLUserProvisioner) -> None:
        """mail 属性。"""
        attrs = {"mail": "user@test.com"}
        assert provisioner._extract_email(attrs, "") == "user@test.com"

    def test_extract_email_oasis_format(self, provisioner: SAMLUserProvisioner) -> None:
        """OASIS 标准属性名。"""
        attrs = {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "user@test.com"
        }
        assert provisioner._extract_email(attrs, "") == "user@test.com"

    def test_extract_email_nameid_fallback(self, provisioner: SAMLUserProvisioner) -> None:
        """NameID 为邮箱格式时作为回退。"""
        assert provisioner._extract_email({}, "user@test.com") == "user@test.com"

    def test_extract_email_no_email_found(self, provisioner: SAMLUserProvisioner) -> None:
        """无邮箱属性且 NameID 非邮箱时返回空字符串。"""
        assert provisioner._extract_email({}, "opaque-nameid") == ""

    def test_extract_email_invalid_email_ignored(
        self, provisioner: SAMLUserProvisioner
    ) -> None:
        """无 @ 的 email 值被忽略。"""
        attrs = {"email": "not-an-email"}
        assert provisioner._extract_email(attrs, "") == ""


# ── 用户名生成测试 ──


class TestGenerateUsername:
    """SAML 用户名生成测试。"""

    def test_generate_from_username_attr(self, provisioner: SAMLUserProvisioner) -> None:
        """优先使用 username 属性。"""
        attrs = {"username": "john.doe"}
        name = provisioner._generate_username("okta", attrs, "nameid-123")
        assert name.startswith(settings.SAML_USERNAME_PREFIX)
        assert "john_doe" in name  # . 被替换为 _

    def test_generate_from_displayname(self, provisioner: SAMLUserProvisioner) -> None:
        """无 username 时使用 displayname。"""
        attrs = {"displayname": "Jane Doe"}
        name = provisioner._generate_username("okta", attrs, "nameid-456")
        assert "Jane_Doe" in name

    def test_generate_from_nameid_local_part(self, provisioner: SAMLUserProvisioner) -> None:
        """无属性时使用 NameID 本地部分。"""
        name = provisioner._generate_username("okta", {}, "user@idp.test")
        assert "user" in name

    def test_generate_cleans_special_chars(
        self, provisioner: SAMLUserProvisioner
    ) -> None:
        """非法字符被替换为下划线。"""
        attrs = {"username": "user@domain.com!"}
        name = provisioner._generate_username("okta", attrs, "nameid")
        assert "@" not in name
        assert "!" not in name

    def test_generate_has_random_suffix(self, provisioner: SAMLUserProvisioner) -> None:
        """用户名含随机后缀确保唯一。"""
        name1 = provisioner._generate_username("okta", {"username": "test"}, "n1")
        name2 = provisioner._generate_username("okta", {"username": "test"}, "n2")
        assert name1 != name2


# ── 元数据测试 ──


class TestProviderMetadata:
    """IdP 元数据查询测试。"""

    def test_get_metadata_all(self, saml_service: SAMLService) -> None:
        """获取所有 IdP 列表。"""
        metadata = saml_service.get_provider_metadata()
        assert "providers" in metadata
        assert len(metadata["providers"]) == 2
        assert metadata["default_provider"] == "okta"

    def test_get_metadata_single(self, saml_service: SAMLService) -> None:
        """获取单个 IdP 元数据。"""
        metadata = saml_service.get_provider_metadata("okta")
        assert metadata["provider"] == "okta"
        assert metadata["entity_id"] == "http://www.okta.com/exk1234567890"
        assert metadata["sso_url"].startswith("https://")

    def test_get_metadata_single_not_found(
        self, saml_service: SAMLService
    ) -> None:
        """未配置的 IdP 抛出 SAMLConfigError。"""
        with pytest.raises(SAMLConfigError):
            saml_service.get_provider_metadata("nonexistent")


# ── 请求上下文构建测试 ──


class TestRequestDataBuilder:
    """python3-saml request_data 构建测试。"""

    def test_build_minimal_request_data(self) -> None:
        """最小占位 request_data 包含必要字段。"""
        data = SAMLService._build_minimal_request_data("/acs")
        assert data["https"] == "on"
        assert data["http_host"] == "localhost"
        assert data["server_port"] == 443
        assert data["script_name"] == "/acs"
        assert data["get_data"] == {}
        assert data["post_data"] == {}

    def test_build_request_data_from_request_https(self) -> None:
        """从 HTTPS Request 构建 request_data。"""
        request = MagicMock()
        request.headers = {"x-forwarded-proto": "https", "host": "app.test.local"}
        request.url.scheme = "http"
        request.url.port = None
        request.url.path = "/api/v1/auth/saml/acs"
        request.query_params = {}

        data = SAMLService.build_request_data_from_request(request)
        assert data["https"] == "on"
        assert data["http_host"] == "app.test.local"
        assert data["server_port"] == 443

    def test_build_request_data_from_request_http(self) -> None:
        """从 HTTP Request 构建 request_data。"""
        request = MagicMock()
        request.headers = {"host": "localhost:8080"}
        request.url.scheme = "http"
        request.url.port = 8080
        request.url.path = "/saml/acs"
        request.query_params = {}

        data = SAMLService.build_request_data_from_request(request)
        assert data["https"] == "off"
        assert data["http_host"] == "localhost:8080"
        assert data["server_port"] == 8080

    def test_build_request_data_with_saml_response(self) -> None:
        """带 SAMLResponse 时 post_data 包含该字段。"""
        request = MagicMock()
        request.headers = {"host": "localhost"}
        request.url.scheme = "https"
        request.url.port = None
        request.url.path = "/acs"
        request.query_params = {}

        data = SAMLService.build_request_data_from_request(
            request, saml_response="base64-encoded-response"
        )
        assert data["post_data"]["SAMLResponse"] == "base64-encoded-response"


# ── SP 元数据 XML 生成测试 ──


class TestSPMetadataGeneration:
    """SP 元数据 XML 生成测试。"""

    def test_generate_sp_metadata_returns_xml(self, saml_service: SAMLService) -> None:
        """generate_sp_metadata 返回有效 XML 字符串。"""
        # SAMLService 在模块顶层导入 generate_sp_metadata_xml，
        # 需 patch app.services.saml_service 命名空间内的引用
        with patch(
            "app.services.saml_service.generate_sp_metadata_xml"
        ) as mock_gen:
            mock_gen.return_value = "<EntityDescriptor>test</EntityDescriptor>"
            xml = saml_service.generate_sp_metadata("okta")
            assert "<EntityDescriptor>" in xml
            mock_gen.assert_called_once()

    def test_generate_sp_metadata_default_provider(
        self, saml_service: SAMLService
    ) -> None:
        """generate_sp_metadata 不传 provider 使用默认 IdP。"""
        with patch(
            "app.services.saml_service.generate_sp_metadata_xml"
        ) as mock_gen:
            mock_gen.return_value = "<EntityDescriptor/>"
            saml_service.generate_sp_metadata(None)
            mock_gen.assert_called_once()

    def test_generate_sp_metadata_real_xml(self, saml_service: SAMLService) -> None:
        """不 mock 时生成真实 SP 元数据 XML（验证集成正确性）。"""
        xml = saml_service.generate_sp_metadata("okta")
        # python3-saml 生成的元数据含 md:EntityDescriptor 命名空间前缀
        assert "EntityDescriptor" in xml
        assert _TEST_SP_ENTITY_ID in xml
        assert _TEST_SP_ACS_URL in xml
