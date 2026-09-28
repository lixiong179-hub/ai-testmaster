"""Phase 3 Task 5: OIDC SSO 适配服务。

业务用途：
    对接企业 IdP（Google/Azure AD/Okta/Keycloak 等），实现 OAuth2/OIDC 标准授权码流程，
    支持单点登录（SSO）与本地账号自动配置（auto-provision）。

核心能力：
    1. 多 IdP 配置管理：从 settings.OIDC_IDP_CONFIGS 加载多个 IdP 配置
    2. 授权码流程：生成授权 URL → 回调换取 token → 解析 id_token / userinfo
    3. state 参数管理：基于 Redis/内存存储 state，CSRF 防护 + TTL 控制
    4. 用户映射：通过 (oidc_issuer, oidc_sub) 查找本地用户；未找到时按配置自动创建
    5. JWT 签发：OIDC 登录成功后签发本平台的 access_token / refresh_token

边界场景：
    - OIDC_SSO_ENABLED=False 时所有方法抛出 ServiceUnavailableError
    - IdP 配置缺失或无效时抛出 ValueError
    - state 校验失败时抛出 AuthenticationError（CSRF 攻击嫌疑）
    - id_token 验签失败时抛出 AuthenticationError（令牌被篡改）
    - OIDC_AUTO_PROVISION=False 且用户未绑定时抛出 AuthenticationError

依赖：
    - authlib (OIDC 客户端实现)
    - app.utils.jwt_utils (本平台 JWT 签发)
    - app.services.session_service (会话治理)

拆分说明（控制单文件行数）：
    - 异常类型 → app.services.oidc_exceptions
    - token 换取 / id_token 解析 → app.services.oidc_token_mixin.OIDCTokenMixin
    - 用户映射 / 自动配置 / 回调 → app.services.oidc_user_mixin.OIDCUserMixin
"""
from __future__ import annotations

import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from app.core.config import settings
from app.services.oidc_exceptions import (
    OIDCConfigError,
    OIDCDisabledError,
    OIDCServiceError,
    OIDCStateError,
    OIDCTokenError,
    OIDCUserNotBoundError,
)
from app.services.oidc_token_mixin import OIDCTokenMixin
from app.services.oidc_user_mixin import OIDCUserMixin

# 向后兼容：异常类型历史从 oidc_service 导入，此处 re-export
__all__ = [
    "OIDCService",
    "OIDCServiceError",
    "OIDCDisabledError",
    "OIDCConfigError",
    "OIDCStateError",
    "OIDCTokenError",
    "OIDCUserNotBoundError",
    "get_oidc_service",
]


def _get_redis_client():
    """延迟获取 Redis 客户端，复用 jwt_utils 的连接配置。

    返回 None 表示 Redis 不可用，调用方应降级到内存存储。
    """
    try:
        import redis
        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            return None
        return redis.from_url(
            redis_url,
            max_connections=10,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
    except Exception as e:
        logger.debug(f"Redis 不可用，OIDC state 降级为内存模式: {e}")
        return None


# 进程内 state 存储（Redis 不可用时的降级方案）
# 结构：{state: {"provider": str, "nonce": str, "expires_at": float}}
_memory_state_store: Dict[str, Dict[str, Any]] = {}


class OIDCService(OIDCTokenMixin, OIDCUserMixin):
    """OIDC SSO 服务。

    封装 OAuth2/OIDC 授权码流程的核心逻辑，支持多 IdP 配置与自动用户配置。

    使用示例：
        service = OIDCService()
        # 1. 生成授权 URL
        auth_url, state = service.build_authorization_url("google", redirect_to="/dashboard")
        # 2. 回调处理
        result = await service.handle_callback(provider="google", code="xxx", state="yyy")
        # result 含 access_token / refresh_token / user 信息
    """

    STATE_REDIS_PREFIX = "oidc:state:"
    NONCE_REDIS_PREFIX = "oidc:nonce:"

    def __init__(self) -> None:
        """初始化 OIDC 服务，校验全局开关与配置。"""
        if not settings.OIDC_SSO_ENABLED:
            raise OIDCDisabledError()
        if not settings.oidc_idp_configs_list:
            raise OIDCConfigError("未配置任何 OIDC IdP，请在 OIDC_IDP_CONFIGS 中至少配置一个")

    # ── IdP 配置管理 ──

    def list_providers(self) -> list:
        """列出所有已配置的 IdP 标识。"""
        return [c["provider"] for c in settings.oidc_idp_configs_list]

    def get_provider_config(self, provider: Optional[str]) -> Dict[str, Any]:
        """获取指定 IdP 配置；provider 为 None 时使用默认 IdP。

        Args:
            provider: IdP 标识；None 表示使用 OIDC_DEFAULT_PROVIDER

        Returns:
            dict: IdP 配置字典

        Raises:
            OIDCConfigError: 配置不存在
        """
        target = provider or settings.OIDC_DEFAULT_PROVIDER
        cfg = settings.get_oidc_provider_config(target)
        if cfg is None:
            available = ", ".join(self.list_providers()) or "(空)"
            raise OIDCConfigError(f"未找到 IdP 配置: provider={target}，可用: {available}")
        return cfg

    def resolve_provider(self, provider: Optional[str]) -> str:
        """解析实际使用的 provider 标识（处理 None 情况）。"""
        return provider or settings.OIDC_DEFAULT_PROVIDER

    # ── state / nonce 管理 ──

    def _generate_state(self) -> str:
        """生成 CSRF 防护用的 state 参数（256-bit 随机）。"""
        return secrets.token_urlsafe(32)

    def _generate_nonce(self) -> str:
        """生成 OIDC nonce 参数（防止重放攻击）。"""
        return secrets.token_urlsafe(32)

    def _store_state(self, state: str, provider: str, nonce: str) -> None:
        """存储 state → (provider, nonce) 映射，带 TTL。"""
        expires_at = time.time() + settings.OIDC_STATE_TTL_SECONDS
        payload = {"provider": provider, "nonce": nonce, "expires_at": expires_at}

        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                redis_client.setex(
                    f"{self.STATE_REDIS_PREFIX}{state}",
                    settings.OIDC_STATE_TTL_SECONDS,
                    json.dumps(payload),
                )
                return
            except Exception as e:
                logger.warning(f"Redis 存储 state 失败，降级为内存: {e}")

        _memory_state_store[state] = payload
        # 清理过期 state（防止内存泄漏）
        self._cleanup_memory_state()

    def _consume_state(self, state: str) -> Optional[Dict[str, Any]]:
        """消费 state（一次性读取后删除），返回存储的 payload。

        Returns:
            Optional[dict]: payload 含 provider/nonce/expires_at；不存在或已过期返回 None
        """
        if not state:
            return None

        redis_client = _get_redis_client()
        if redis_client is not None:
            try:
                key = f"{self.STATE_REDIS_PREFIX}{state}"
                raw = redis_client.get(key)
                if raw is None:
                    return None
                redis_client.delete(key)
                payload = json.loads(raw)
                if payload.get("expires_at", 0) < time.time():
                    return None
                return payload
            except Exception as e:
                logger.warning(f"Redis 读取 state 失败，降级为内存: {e}")

        payload = _memory_state_store.pop(state, None)
        if payload is None:
            return None
        if payload.get("expires_at", 0) < time.time():
            return None
        return payload

    def _cleanup_memory_state(self) -> None:
        """清理内存中过期的 state 条目。"""
        now = time.time()
        expired = [k for k, v in _memory_state_store.items() if v.get("expires_at", 0) < now]
        for k in expired:
            _memory_state_store.pop(k, None)

    # ── 授权码流程 ──

    def build_authorization_url(
        self,
        provider: Optional[str] = None,
        redirect_to: Optional[str] = None,
    ) -> Tuple[str, str]:
        """构造 OIDC 授权 URL（用户点击后跳转到 IdP 登录页）。

        Args:
            provider: IdP 标识；None 使用默认 IdP
            redirect_to: 登录成功后前端跳转目标路径（存入 state，回调后回传前端）

        Returns:
            tuple[str, str]: (授权 URL, state)
        """
        actual_provider = self.resolve_provider(provider)
        cfg = self.get_provider_config(actual_provider)

        state = self._generate_state()
        nonce = self._generate_nonce()
        # redirect_to 作为 state 上下文的一部分（回调后前端跳转用）
        # 不存入 IdP 可见的 state 参数，仅存入服务端 state → nonce 映射
        self._store_state(state, actual_provider, nonce)

        # 构造授权 URL（OAuth2 Authorization Code Flow）
        # 不依赖 authlib 的 AsyncOAuth2Client.create_authorization_url，
        # 直接构造 URL 以避免 IdP discovery 失败的硬依赖（兼容静态 issuer）
        authorization_endpoint = cfg.get(
            "authorization_endpoint",
            self._derive_authorization_endpoint(cfg),
        )
        scopes = cfg.get("scopes", "openid email profile")
        redirect_uri = cfg["redirect_uri"]
        client_id = cfg["client_id"]

        # 标准 OIDC 授权参数
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
            "nonce": nonce,
        }
        # 拼接到 IdP 授权端点
        from urllib.parse import urlencode

        query = urlencode(params)
        auth_url = f"{authorization_endpoint}?{query}"

        logger.info(
            f"OIDC 授权 URL 已生成: provider={actual_provider} state={state[:8]}... "
            f"redirect_to={redirect_to}"
        )
        return auth_url, state

    def _derive_authorization_endpoint(self, cfg: Dict[str, Any]) -> str:
        """从 issuer 或 discovery_url 推导授权端点 URL。

        优先级：authorization_endpoint（显式） > discovery_url 推导 > issuer + /authorize
        """
        # 显式配置优先
        explicit = cfg.get("authorization_endpoint")
        if explicit:
            return explicit
        discovery = cfg.get("discovery_url")
        if discovery:
            # 假设 discovery 文档位于 /authorize 子路径，需运行时获取；
            # 此处降级返回 discovery_url 自身（生产建议显式配置 authorization_endpoint）
            return discovery.replace(
                "/.well-known/openid-configuration", "/authorize"
            ) if discovery.endswith("/.well-known/openid-configuration") else discovery
        issuer = cfg.get("issuer", "").rstrip("/")
        return f"{issuer}/authorize"

    def _derive_token_endpoint(self, cfg: Dict[str, Any]) -> str:
        """推导 token 端点 URL。优先级：token_endpoint > discovery > issuer + /token。"""
        explicit = cfg.get("token_endpoint")
        if explicit:
            return explicit
        discovery = cfg.get("discovery_url")
        if discovery:
            return discovery.replace(
                "/.well-known/openid-configuration", "/token"
            ) if discovery.endswith("/.well-known/openid-configuration") else discovery
        issuer = cfg.get("issuer", "").rstrip("/")
        return f"{issuer}/token"

    def _derive_userinfo_endpoint(self, cfg: Dict[str, Any]) -> str:
        """推导 userinfo 端点 URL。优先级：userinfo_endpoint > discovery > issuer + /userinfo。"""
        explicit = cfg.get("userinfo_endpoint")
        if explicit:
            return explicit
        discovery = cfg.get("discovery_url")
        if discovery:
            return discovery.replace(
                "/.well-known/openid-configuration", "/userinfo"
            ) if discovery.endswith("/.well-known/openid-configuration") else discovery
        issuer = cfg.get("issuer", "").rstrip("/")
        return f"{issuer}/userinfo"


# 模块级单例（延迟初始化，避免 import 时抛异常）
_oidc_service_instance: Optional[OIDCService] = None


def get_oidc_service() -> OIDCService:
    """获取 OIDCService 单例。

    每次调用都重新创建实例以读取最新配置（支持运行时配置热更新）。
    若 OIDC_SSO_ENABLED=False 则抛出 OIDCDisabledError。
    """
    return OIDCService()
