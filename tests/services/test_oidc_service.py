"""Phase 3 Task 5: OIDC SSO 适配服务单元测试。

覆盖：
    - OIDCService 初始化: 禁用模式 / 未配置 IdP / 启用模式
    - IdP 配置管理: list_providers / get_provider_config / resolve_provider
    - state 管理: 生成 / 存储 / 消费 / 过期 / 一次性
    - 授权 URL 构造: 标准 OIDC 参数 / 自定义 IdP / 推导端点
    - id_token 解析: 未配置 jwks 时跳过验签 / nonce 校验失败
    - 用户映射: 按 (issuer,sub) 查找 / 按 email 绑定 / 自动创建新用户 / 禁止自动注册
    - 用户名生成: 优先 preferred_username / 清理非法字符 / 唯一后缀
    - 元数据: 单个 IdP / 列表 / 脱敏
"""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

# R4-4：authlib 未安装时整文件 skip，而非 fail —— 属环境依赖缺失，非代码缺陷
pytest.importorskip("authlib", reason="环境未安装 authlib，非代码缺陷")

from app.core.config import settings
from app.services.oidc_service import (
    OIDCConfigError,
    OIDCDisabledError,
    OIDCService,
    OIDCStateError,
    OIDCTokenError,
    OIDCUserNotBoundError,
    _memory_state_store,
    get_oidc_service,
)


# ── 测试用 IdP 配置 ──

_TEST_IDP_CONFIGS = [
    {
        "provider": "google",
        "client_id": "google-client-id",
        "client_secret": "google-secret",
        "issuer": "https://accounts.google.com",
        "scopes": "openid email profile",
        "redirect_uri": "http://localhost:5173/api/v1/auth/oidc/callback",
    },
    {
        "provider": "azure",
        "client_id": "azure-client-id",
        "client_secret": "azure-secret",
        "issuer": "https://login.microsoftonline.com/tenant-id/v2.0",
        "scopes": "openid email profile",
        "redirect_uri": "http://localhost:5173/api/v1/auth/oidc/callback",
    },
]


@pytest.fixture
def oidc_enabled(monkeypatch):
    """启用 OIDC 并配置测试 IdP。"""
    monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", True)
    monkeypatch.setattr(
        settings, "OIDC_IDP_CONFIGS", json.dumps(_TEST_IDP_CONFIGS)
    )
    monkeypatch.setattr(settings, "OIDC_DEFAULT_PROVIDER", "google")
    # 清空内存 state 存储
    _memory_state_store.clear()
    yield
    _memory_state_store.clear()


@pytest.fixture
def oidc_service(oidc_enabled) -> OIDCService:
    """创建 OIDCService 实例（已启用）。"""
    return OIDCService()


# ── 初始化测试 ──


class TestOIDCServiceInit:
    """OIDCService 初始化测试。"""

    def test_init_raises_when_disabled(self, monkeypatch) -> None:
        """OIDC_SSO_ENABLED=False 时抛出 OIDCDisabledError。"""
        monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", False)
        with pytest.raises(OIDCDisabledError):
            OIDCService()

    def test_init_raises_when_no_idp_configured(
        self, monkeypatch
    ) -> None:
        """OIDC_IDP_CONFIGS 为空时抛出 OIDCConfigError。"""
        monkeypatch.setattr(settings, "OIDC_SSO_ENABLED", True)
        monkeypatch.setattr(settings, "OIDC_IDP_CONFIGS", "[]")
        with pytest.raises(OIDCConfigError, match="未配置任何 OIDC IdP"):
            OIDCService()

    def test_get_oidc_service_factory_returns_instance(self, oidc_enabled) -> None:
        """get_oidc_service 工厂函数返回实例。"""
        service = get_oidc_service()
        assert isinstance(service, OIDCService)


# ── IdP 配置管理测试 ──


class TestProviderConfig:
    """IdP 配置管理测试。"""

    def test_list_providers(self, oidc_service: OIDCService) -> None:
        """list_providers 返回所有配置的 IdP 标识。"""
        providers = oidc_service.list_providers()
        assert providers == ["google", "azure"]

    def test_get_provider_config_existing(self, oidc_service: OIDCService) -> None:
        """get_provider_config 返回指定 IdP 配置。"""
        cfg = oidc_service.get_provider_config("google")
        assert cfg["provider"] == "google"
        assert cfg["client_id"] == "google-client-id"
        assert cfg["client_secret"] == "google-secret"

    def test_get_provider_config_default(self, oidc_service: OIDCService) -> None:
        """provider=None 时返回默认 IdP 配置。"""
        cfg = oidc_service.get_provider_config(None)
        assert cfg["provider"] == "google"

    def test_get_provider_config_not_found(self, oidc_service: OIDCService) -> None:
        """未配置的 IdP 抛出 OIDCConfigError。"""
        with pytest.raises(OIDCConfigError, match="未找到 IdP 配置"):
            oidc_service.get_provider_config("nonexistent")

    def test_resolve_provider_with_value(self, oidc_service: OIDCService) -> None:
        """resolve_provider 透传非 None 值。"""
        assert oidc_service.resolve_provider("azure") == "azure"

    def test_resolve_provider_none_uses_default(
        self, oidc_service: OIDCService
    ) -> None:
        """resolve_provider(None) 返回默认 IdP。"""
        assert oidc_service.resolve_provider(None) == "google"


# ── state 管理测试 ──


class TestStateManagement:
    """state / nonce 管理测试。"""

    def test_generate_state_unique(self, oidc_service: OIDCService) -> None:
        """生成的 state 唯一且足够长。"""
        states = {oidc_service._generate_state() for _ in range(20)}
        assert len(states) == 20
        for s in states:
            assert len(s) >= 32

    def test_generate_nonce_unique(self, oidc_service: OIDCService) -> None:
        """生成的 nonce 唯一。"""
        nonces = {oidc_service._generate_nonce() for _ in range(20)}
        assert len(nonces) == 20

    def test_store_and_consume_state(self, oidc_service: OIDCService) -> None:
        """存储后消费返回 payload。"""
        oidc_service._store_state("state-1", "google", "nonce-1")
        payload = oidc_service._consume_state("state-1")
        assert payload is not None
        assert payload["provider"] == "google"
        assert payload["nonce"] == "nonce-1"
        assert "expires_at" in payload

    def test_consume_state_one_time(self, oidc_service: OIDCService) -> None:
        """state 只能消费一次（防重放）。"""
        oidc_service._store_state("state-2", "google", "nonce-2")
        first = oidc_service._consume_state("state-2")
        second = oidc_service._consume_state("state-2")
        assert first is not None
        assert second is None

    def test_consume_nonexistent_state(self, oidc_service: OIDCService) -> None:
        """消费不存在的 state 返回 None。"""
        assert oidc_service._consume_state("nonexistent") is None

    def test_consume_empty_state(self, oidc_service: OIDCService) -> None:
        """消费空 state 返回 None。"""
        assert oidc_service._consume_state("") is None
        assert oidc_service._consume_state(None) is None

    def test_consume_expired_state(self, oidc_service: OIDCService, monkeypatch) -> None:
        """过期的 state 返回 None。"""
        # 手动注入已过期的 state
        _memory_state_store["expired-state"] = {
            "provider": "google",
            "nonce": "nonce-x",
            "expires_at": time.time() - 100,  # 100 秒前过期
        }
        assert oidc_service._consume_state("expired-state") is None

    def test_cleanup_memory_state(self, oidc_service: OIDCService) -> None:
        """_cleanup_memory_state 清理过期条目。"""
        _memory_state_store["valid"] = {
            "provider": "google",
            "nonce": "n",
            "expires_at": time.time() + 100,
        }
        _memory_state_store["expired"] = {
            "provider": "google",
            "nonce": "n",
            "expires_at": time.time() - 100,
        }
        oidc_service._cleanup_memory_state()
        assert "valid" in _memory_state_store
        assert "expired" not in _memory_state_store


# ── 授权 URL 构造测试 ──


class TestAuthorizationUrl:
    """授权 URL 构造测试。"""

    def test_build_authorization_url_default_provider(
        self, oidc_service: OIDCService
    ) -> None:
        """默认 IdP 构造的授权 URL 含标准 OIDC 参数。"""
        url, state = oidc_service.build_authorization_url()
        assert state  # 非空
        assert url.startswith("https://accounts.google.com/authorize?")
        assert "response_type=code" in url
        assert "client_id=google-client-id" in url
        assert "scope=openid+email+profile" in url or "scope=openid" in url
        assert f"state={state}" in url
        assert "nonce=" in url

    def test_build_authorization_url_custom_provider(
        self, oidc_service: OIDCService
    ) -> None:
        """指定 IdP 构造的授权 URL 使用对应配置。"""
        url, state = oidc_service.build_authorization_url(provider="azure")
        assert url.startswith("https://login.microsoftonline.com/tenant-id/v2.0/authorize?")
        assert "client_id=azure-client-id" in url

    def test_build_authorization_url_unknown_provider(
        self, oidc_service: OIDCService
    ) -> None:
        """未知 IdP 抛出 OIDCConfigError。"""
        with pytest.raises(OIDCConfigError):
            oidc_service.build_authorization_url(provider="unknown")

    def test_derive_authorization_endpoint_from_discovery(
        self, oidc_service: OIDCService
    ) -> None:
        """discovery_url 末尾 /.well-known/openid-configuration 时推导 /authorize。"""
        cfg = {
            "provider": "test",
            "discovery_url": "https://idp.example.com/.well-known/openid-configuration",
        }
        endpoint = oidc_service._derive_authorization_endpoint(cfg)
        assert endpoint == "https://idp.example.com/authorize"

    def test_derive_authorization_endpoint_from_issuer(
        self, oidc_service: OIDCService
    ) -> None:
        """仅配置 issuer 时推导 issuer + /authorize。"""
        cfg = {"provider": "test", "issuer": "https://idp.example.com/"}
        endpoint = oidc_service._derive_authorization_endpoint(cfg)
        assert endpoint == "https://idp.example.com/authorize"

    def test_derive_token_endpoint(self, oidc_service: OIDCService) -> None:
        """推导 token 端点。"""
        cfg = {"provider": "test", "issuer": "https://idp.example.com"}
        assert oidc_service._derive_token_endpoint(cfg) == "https://idp.example.com/token"

    def test_derive_userinfo_endpoint(self, oidc_service: OIDCService) -> None:
        """推导 userinfo 端点。"""
        cfg = {"provider": "test", "issuer": "https://idp.example.com"}
        assert (
            oidc_service._derive_userinfo_endpoint(cfg)
            == "https://idp.example.com/userinfo"
        )

    def test_explicit_endpoints_take_precedence(
        self, oidc_service: OIDCService
    ) -> None:
        """显式配置的端点优先于推导。"""
        cfg = {
            "provider": "test",
            "issuer": "https://idp.example.com",
            "authorization_endpoint": "https://custom.example.com/auth",
            "token_endpoint": "https://custom.example.com/token",
            "userinfo_endpoint": "https://custom.example.com/me",
        }
        assert oidc_service._derive_authorization_endpoint(cfg) == "https://custom.example.com/auth"
        assert oidc_service._derive_token_endpoint(cfg) == "https://custom.example.com/token"
        assert oidc_service._derive_userinfo_endpoint(cfg) == "https://custom.example.com/me"


# ── id_token 解析测试 ──


class TestParseIdToken:
    """id_token 解析测试。"""

    def test_parse_id_token_without_jwks_skips_verification(
        self, oidc_service: OIDCService
    ) -> None:
        """未配置 jwks 时跳过验签，直接解析 claims（开发模式）。"""
        import base64
        import json as _json

        # 构造未签名的 JWT（alg=none）
        header = base64.urlsafe_b64encode(
            _json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            _json.dumps(
                {
                    "sub": "user-123",
                    "iss": "https://accounts.google.com",
                    "aud": "google-client-id",
                    "email": "user@example.com",
                    "name": "Test User",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time()),
                }
            ).encode()
        ).decode().rstrip("=")
        unsigned_jwt = f"{header}.{payload}."

        # 调用 service 实际方法（未配置 jwks 走跳过验签分支）
        claims = oidc_service.parse_id_token("google", unsigned_jwt)
        assert claims["sub"] == "user-123"
        assert claims["email"] == "user@example.com"
        assert claims["name"] == "Test User"

    def test_parse_id_token_nonce_mismatch_raises(
        self, oidc_service: OIDCService
    ) -> None:
        """nonce 不匹配时抛出 OIDCTokenError。"""
        import base64
        import json as _json

        # 构造 JWT 含 nonce="stored-nonce"
        header = base64.urlsafe_b64encode(
            _json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            _json.dumps(
                {
                    "sub": "user-456",
                    "iss": "https://accounts.google.com",
                    "aud": "google-client-id",
                    "nonce": "stored-nonce",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time()),
                }
            ).encode()
        ).decode().rstrip("=")
        unsigned_jwt = f"{header}.{payload}."

        # 传入不匹配的 nonce 应抛出 OIDCTokenError
        with pytest.raises(OIDCTokenError, match="nonce"):
            oidc_service.parse_id_token(
                "google", unsigned_jwt, nonce="wrong-nonce"
            )

    def test_parse_id_token_with_matching_nonce_passes(
        self, oidc_service: OIDCService
    ) -> None:
        """nonce 匹配时不抛出异常。"""
        import base64
        import json as _json

        header = base64.urlsafe_b64encode(
            _json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            _json.dumps(
                {
                    "sub": "user-789",
                    "iss": "https://accounts.google.com",
                    "aud": "google-client-id",
                    "nonce": "correct-nonce",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time()),
                }
            ).encode()
        ).decode().rstrip("=")
        unsigned_jwt = f"{header}.{payload}."

        claims = oidc_service.parse_id_token(
            "google", unsigned_jwt, nonce="correct-nonce"
        )
        assert claims["sub"] == "user-789"

    def test_parse_id_token_invalid_jwt_raises(
        self, oidc_service: OIDCService
    ) -> None:
        """无效 JWT 抛出 OIDCTokenError。"""
        with pytest.raises(OIDCTokenError, match="id_token"):
            oidc_service.parse_id_token("google", "not-a-valid-jwt")


# ── 用户映射测试 ──


class TestUserProvisioning:
    """用户映射与自动配置测试。"""

    @pytest.mark.asyncio
    async def test_find_user_by_oidc_existing(
        self, oidc_service: OIDCService, db, sync_backed_async_db
    ) -> None:
        """按 (issuer, sub) 查找已绑定用户。"""
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        user = User(
            username="sso_existing_user",
            email="sso_existing@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            oidc_issuer="https://accounts.google.com",
            oidc_sub="sub-123",
            oidc_provider="google",
        )
        db.add(user)
        db.flush()

        try:
            found = await oidc_service.find_user_by_oidc(
                sync_backed_async_db, "https://accounts.google.com", "sub-123"
            )
            assert found is not None
            assert found.id == user.id
        finally:
            db.query(User).filter(User.id == user.id).delete()
            db.flush()

    @pytest.mark.asyncio
    async def test_find_user_by_oidc_not_found(
        self, oidc_service: OIDCService, sync_backed_async_db
    ) -> None:
        """未绑定的 (issuer, sub) 返回 None。"""
        found = await oidc_service.find_user_by_oidc(
            sync_backed_async_db, "https://unknown.idp.com", "nonexistent-sub"
        )
        assert found is None

    @pytest.mark.asyncio
    async def test_find_user_by_email_existing(
        self, oidc_service: OIDCService, db, sync_backed_async_db
    ) -> None:
        """按 email 查找本地用户。"""
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        user = User(
            username="sso_email_user",
            email="sso_email_unique@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        try:
            found = await oidc_service.find_user_by_email(sync_backed_async_db, "sso_email_unique@test.com")
            assert found is not None
            assert found.id == user.id
        finally:
            db.query(User).filter(User.id == user.id).delete()
            db.flush()

    @pytest.mark.asyncio
    async def test_provision_user_binds_existing_by_oidc(
        self, oidc_service: OIDCService, db, sync_backed_async_db
    ) -> None:
        """已绑定 (issuer, sub) 的用户直接返回。"""
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        user = User(
            username="sso_provision_bound",
            email="sso_provision_bound@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
            oidc_issuer="https://accounts.google.com",
            oidc_sub="sub-bound",
            oidc_provider="google",
        )
        db.add(user)
        db.flush()

        try:
            claims = {"sub": "sub-bound", "email": "newemail@test.com", "name": "Test"}
            result = await oidc_service.provision_user(
                sync_backed_async_db, "google", "https://accounts.google.com", claims
            )
            assert result.id == user.id
            # 已绑定用户不应更新 email
            assert result.email == "sso_provision_bound@test.com"
        finally:
            db.query(User).filter(User.id == user.id).delete()
            db.flush()

    @pytest.mark.asyncio
    async def test_provision_user_binds_existing_by_email(
        self, oidc_service: OIDCService, db, sync_backed_async_db
    ) -> None:
        """未绑定但 email 匹配的本地用户自动绑定。"""
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        user = User(
            username="sso_email_bind",
            email="sso_email_bind@test.com",
            password_hash=get_password_hash("Test@123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        try:
            claims = {
                "sub": "sub-new",
                "email": "sso_email_bind@test.com",
                "email_verified": True,
                "name": "Test",
            }
            result = await oidc_service.provision_user(
                sync_backed_async_db, "google", "https://accounts.google.com", claims
            )
            assert result.id == user.id
            assert result.oidc_sub == "sub-new"
            assert result.oidc_issuer == "https://accounts.google.com"
            assert result.oidc_provider == "google"
        finally:
            db.query(User).filter(User.id == user.id).delete()
            db.flush()

    @pytest.mark.asyncio
    async def test_provision_user_creates_new_user(
        self, oidc_service: OIDCService, db, sync_backed_async_db
    ) -> None:
        """未绑定且无匹配 email 时创建新用户。"""
        from app.models.user import User

        claims = {
            "sub": f"sub-create-{int(time.time())}",
            "email": f"newuser-{int(time.time())}@test.com",
            "name": "New User",
            "preferred_username": "newuser",
        }
        result = await oidc_service.provision_user(
            sync_backed_async_db, "google", "https://accounts.google.com", claims
        )
        try:
            assert result.id is not None
            assert result.oidc_sub == claims["sub"]
            assert result.oidc_provider == "google"
            assert result.oidc_issuer == "https://accounts.google.com"
            assert result.is_active is True
            assert result.is_superuser is False
            assert result.username.startswith(settings.OIDC_USERNAME_PREFIX)
        finally:
            db.query(User).filter(User.id == result.id).delete()
            db.flush()

    @pytest.mark.asyncio
    async def test_provision_user_disabled_auto_provision(
        self, oidc_service: OIDCService, sync_backed_async_db, monkeypatch
    ) -> None:
        """OIDC_AUTO_PROVISION=False 且未绑定时抛出 OIDCUserNotBoundError。"""
        monkeypatch.setattr(settings, "OIDC_AUTO_PROVISION", False)
        claims = {
            "sub": "sub-not-bound",
            "email": "notbound@test.com",
        }
        with pytest.raises(OIDCUserNotBoundError):
            await oidc_service.provision_user(
                sync_backed_async_db, "google", "https://accounts.google.com", claims
            )

    @pytest.mark.asyncio
    async def test_provision_user_missing_sub_raises(
        self, oidc_service: OIDCService, sync_backed_async_db
    ) -> None:
        """claims 缺少 sub 字段抛出 OIDCConfigError。"""
        claims = {"email": "nosub@test.com"}
        with pytest.raises(OIDCConfigError, match="缺少 sub"):
            await oidc_service.provision_user(
                sync_backed_async_db, "google", "https://accounts.google.com", claims
            )


# ── 用户名生成测试 ──


class TestUsernameGeneration:
    """用户名生成测试。"""

    def test_preferred_username_used(self, oidc_service: OIDCService) -> None:
        """优先使用 preferred_username。"""
        claims = {"preferred_username": "alice", "sub": "sub-1"}
        username = oidc_service._generate_username("google", claims)
        assert username.startswith(settings.OIDC_USERNAME_PREFIX + "alice_")

    def test_name_used_when_no_preferred(self, oidc_service: OIDCService) -> None:
        """无 preferred_username 时使用 name。"""
        claims = {"name": "Bob Smith", "sub": "sub-2"}
        username = oidc_service._generate_username("google", claims)
        # 空格被替换为下划线
        assert "Bob_Smith" in username

    def test_given_name_used_when_no_name(self, oidc_service: OIDCService) -> None:
        """无 name 时使用 given_name。"""
        claims = {"given_name": "Charlie", "sub": "sub-3"}
        username = oidc_service._generate_username("google", claims)
        assert "Charlie" in username

    def test_provider_sub_used_when_no_claims(
        self, oidc_service: OIDCService
    ) -> None:
        """无任何用户名 claims 时使用 provider + sub。"""
        claims = {"sub": "abcdef1234567890"}
        username = oidc_service._generate_username("google", claims)
        assert "google_abcdef12" in username

    def test_illegal_chars_replaced(self, oidc_service: OIDCService) -> None:
        """非法字符被替换为下划线。"""
        claims = {"preferred_username": "user@domain.com!", "sub": "sub-4"}
        username = oidc_service._generate_username("google", claims)
        # @ 和 ! 和 . 都应被替换
        assert "@" not in username
        assert "!" not in username

    def test_username_has_unique_suffix(self, oidc_service: OIDCService) -> None:
        """用户名含唯一后缀。"""
        claims = {"preferred_username": "dave", "sub": "sub-5"}
        usernames = {
            oidc_service._generate_username("google", claims) for _ in range(10)
        }
        # 由于随机后缀，10 次生成的用户名应几乎都不同
        assert len(usernames) >= 8

    def test_username_truncated(self, oidc_service: OIDCService) -> None:
        """过长的 base 部分被截断。"""
        long_name = "a" * 100
        claims = {"preferred_username": long_name, "sub": "sub-6"}
        username = oidc_service._generate_username("google", claims)
        # base 截断到 30 字符，加上 prefix + suffix + 下划线
        # 格式：{prefix}{base[:30]}_{6hex}
        without_prefix = username[len(settings.OIDC_USERNAME_PREFIX):]
        # 30 (base) + 1 (underscore) + 6 (hex) = 37
        assert len(without_prefix) <= 37


# ── 元数据端点测试 ──


class TestProviderMetadata:
    """IdP 元数据测试。"""

    def test_get_all_metadata(self, oidc_service: OIDCService) -> None:
        """不指定 provider 返回所有 IdP 列表。"""
        metadata = oidc_service.get_provider_metadata()
        assert "providers" in metadata
        assert len(metadata["providers"]) == 2
        assert metadata["default_provider"] == "google"
        providers = [p["provider"] for p in metadata["providers"]]
        assert "google" in providers
        assert "azure" in providers

    def test_get_single_metadata(self, oidc_service: OIDCService) -> None:
        """指定 provider 返回单个 IdP 元数据。"""
        metadata = oidc_service.get_provider_metadata("google")
        assert metadata["provider"] == "google"
        assert metadata["client_id"] == "google-client-id"
        assert metadata["issuer"] == "https://accounts.google.com"
        assert metadata["scopes"] == "openid email profile"
        assert "client_secret" not in metadata  # 脱敏

    def test_get_metadata_unknown_provider(
        self, oidc_service: OIDCService
    ) -> None:
        """未知 provider 抛出 OIDCConfigError。"""
        with pytest.raises(OIDCConfigError):
            oidc_service.get_provider_metadata("unknown")

    def test_metadata_includes_authorization_endpoint(
        self, oidc_service: OIDCService
    ) -> None:
        """元数据包含推导的 authorization_endpoint。"""
        metadata = oidc_service.get_provider_metadata("google")
        assert metadata["authorization_endpoint"] == "https://accounts.google.com/authorize"


# ── exchange_code_for_tokens 测试 ──


class TestExchangeCodeForTokens:
    """授权码换取 token 测试。"""

    @pytest.mark.asyncio
    async def test_exchange_with_invalid_state_raises(
        self, oidc_service: OIDCService
    ) -> None:
        """无效 state 抛出 OIDCStateError。"""
        with pytest.raises(OIDCStateError, match="state 不存在"):
            await oidc_service.exchange_code_for_tokens(
                "google", "code-1", "invalid-state"
            )

    @pytest.mark.asyncio
    async def test_exchange_with_expired_state_raises(
        self, oidc_service: OIDCService
    ) -> None:
        """过期 state 抛出 OIDCStateError。"""
        _memory_state_store["expired"] = {
            "provider": "google",
            "nonce": "n",
            "expires_at": time.time() - 100,
        }
        with pytest.raises(OIDCStateError):
            await oidc_service.exchange_code_for_tokens(
                "google", "code-1", "expired"
            )

    @pytest.mark.asyncio
    async def test_exchange_with_provider_mismatch_raises(
        self, oidc_service: OIDCService
    ) -> None:
        """state 与 provider 不匹配抛出 OIDCStateError。"""
        oidc_service._store_state("state-mismatch", "google", "nonce")
        with pytest.raises(OIDCStateError, match="不匹配"):
            await oidc_service.exchange_code_for_tokens(
                "azure", "code-1", "state-mismatch"
            )
