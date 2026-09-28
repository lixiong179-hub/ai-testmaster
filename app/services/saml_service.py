"""Phase 3 Task 4: SAML 2.0 SSO SP 服务。

对接企业 SAML IdP（Okta/Azure AD/ADFS 等），实现 SP 发起的 SSO 登录、
用户自动配置与 Single Logout。依赖 python3-saml 延迟导入。

模块拆分：
    - saml/_settings_builder: SP/IdP Settings 字典构建
    - saml/_protocol: AuthnRequest / Response / SLO 协议操作
    - saml/_relay_state: RelayState 存储管理（Redis + 内存降级）
    - saml/_user_provisioning: 用户映射与自动配置
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exception._base import BaseAPIException
from app.models.user import User
from app.services.saml import (
    build_authn_request_redirect,
    build_logout_request_redirect,
    generate_sp_metadata_xml,
    parse_logout_response,
    parse_saml_response,
)
from app.services.saml._relay_state import RelayStateStore
from app.services.saml._user_provisioning import SAMLUserProvisioner
from app.utils.db_time import utcnow
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token_with_jti,
)


class SAMLServiceError(BaseAPIException):
    """SAML 服务异常基类。"""

    def __init__(self, msg: str, code: int = 400, details: Optional[dict] = None) -> None:
        super().__init__(msg=msg, code=code, details=details)


class SAMLDisabledError(SAMLServiceError):
    """SAML 功能未启用异常。"""

    def __init__(self) -> None:
        super().__init__(msg="SAML SSO 未启用", code=503)


class SAMLConfigError(SAMLServiceError):
    """SAML IdP 配置异常。"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg, code=400)


class SAMLResponseError(SAMLServiceError):
    """SAMLResponse / LogoutResponse 校验异常。"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg, code=401)


class SAMLRelayStateError(SAMLServiceError):
    """RelayState 校验异常（CSRF 攻击嫌疑）。"""

    def __init__(self, msg: str = "RelayState 校验失败") -> None:
        super().__init__(msg=msg, code=400)


class SAMLUserNotBoundError(SAMLServiceError):
    """SAML 用户未绑定本地账号且不允许自动注册。"""

    def __init__(self, msg: str = "用户未绑定本地账号，请联系管理员开通") -> None:
        super().__init__(msg=msg, code=403)


def get_saml_service() -> "SAMLService":
    """获取 SAMLService 实例（工厂函数）。

    Raises:
        SAMLDisabledError: SAML_SSO_ENABLED=False
        SAMLConfigError: 未配置任何 IdP 或 SP 配置不完整
    """
    return SAMLService()


class SAMLService:
    """SAML 2.0 SSO SP 服务。

    封装 SP 发起的 SSO 流程，支持多 IdP 配置与自动用户配置。

    使用示例：
        service = SAMLService()
        xml = service.generate_sp_metadata("okta")
        redirect_url, relay_state = service.build_login_redirect("okta")
        result = await service.handle_acs(db, "okta", saml_response, relay_state, request_data)
    """

    def __init__(self) -> None:
        """初始化 SAML 服务，校验全局开关与配置。"""
        if not settings.SAML_SSO_ENABLED:
            raise SAMLDisabledError()
        if not settings.saml_idp_configs_list:
            raise SAMLConfigError("未配置任何 SAML IdP，请在 SAML_IDP_CONFIGS 中至少配置一个")
        if not settings.SAML_SP_ENTITY_ID or not settings.SAML_SP_ACS_URL:
            raise SAMLConfigError("SAML SP 配置不完整：需配置 SAML_SP_ENTITY_ID 和 SAML_SP_ACS_URL")
        self._relay_store = RelayStateStore()
        self._provisioner = SAMLUserProvisioner()

    # ── IdP 配置管理 ──

    def list_providers(self) -> list:
        """列出所有已配置的 IdP 标识。"""
        return [c["provider"] for c in settings.saml_idp_configs_list]

    def get_provider_config(self, provider: Optional[str]) -> Dict[str, Any]:
        """获取指定 IdP 配置；provider 为 None 时使用默认 IdP。"""
        target = provider or settings.SAML_DEFAULT_PROVIDER
        cfg = settings.get_saml_provider_config(target)
        if cfg is None:
            available = ", ".join(self.list_providers()) or "(空)"
            raise SAMLConfigError(f"未找到 IdP 配置: provider={target}，可用: {available}")
        return cfg

    def resolve_provider(self, provider: Optional[str]) -> str:
        """解析实际使用的 provider 标识（处理 None 情况）。"""
        return provider or settings.SAML_DEFAULT_PROVIDER

    # ── 请求上下文构建 ──

    @staticmethod
    def build_request_data_from_request(
        request,
        saml_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从 FastAPI Request 构建 python3-saml 要求的 request_data 字典。"""
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        scheme = forwarded_proto or request.url.scheme
        host = request.headers.get("host", "localhost")
        return {
            "https": "on" if scheme == "https" else "off",
            "http_host": host,
            "server_port": request.url.port or (443 if scheme == "https" else 80),
            "script_name": request.url.path,
            "path_info": "",
            "get_data": dict(request.query_params),
            "post_data": {"SAMLResponse": saml_response} if saml_response else {},
        }

    @staticmethod
    def _build_minimal_request_data(script_name: str) -> Dict[str, Any]:
        """构造最小占位 request_data（无实际 HTTP 请求上下文时使用）。"""
        return {
            "https": "on",
            "http_host": "localhost",
            "server_port": 443,
            "script_name": script_name,
            "path_info": "",
            "get_data": {},
            "post_data": {},
        }

    # ── SP 元数据 ──

    def generate_sp_metadata(self, provider: Optional[str] = None) -> str:
        """生成 SP 元数据 XML（供 IdP 导入配置 SP 信任关系）。"""
        idp_cfg = self.get_provider_config(provider)
        return generate_sp_metadata_xml(idp_cfg, strict=True)

    # ── SP 发起 SSO 登录 ──

    def build_login_redirect(
        self,
        provider: Optional[str] = None,
        redirect_to: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """构造 SAML AuthnRequest 跳转 URL（SP 发起 SSO）。

        Args:
            provider: IdP 标识；None 使用默认 IdP
            redirect_to: 登录成功后前端跳转目标路径（存入 RelayState 上下文）
            request_data: python3-saml 请求上下文；None 时使用最小占位

        Returns:
            tuple[str, str]: (IdP 跳转 URL, RelayState)
        """
        actual_provider = self.resolve_provider(provider)
        idp_cfg = self.get_provider_config(actual_provider)
        relay_state = self._relay_store.generate()
        self._relay_store.save(relay_state, actual_provider, redirect_to)

        if request_data is None:
            request_data = self._build_minimal_request_data(settings.SAML_SP_ACS_URL)
        redirect_url = build_authn_request_redirect(
            request_data, idp_cfg, relay_state, strict=True
        )
        logger.info(
            f"SAML 登录跳转: provider={actual_provider} relay_state={relay_state[:8]}..."
        )
        return redirect_url, relay_state

    # ── ACS 回调处理 ──

    async def handle_acs(
        self,
        db: AsyncSession,
        provider: str,
        saml_response: str,
        relay_state: str,
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理 ACS 回调（校验 RelayState → 解析 SAMLResponse → 用户映射 → 签发 token）。

        Raises:
            SAMLRelayStateError / SAMLResponseError / SAMLUserNotBoundError
        """
        # 1. 校验 RelayState（CSRF 防护）
        relay_payload = self._relay_store.consume(relay_state)
        if relay_payload is None:
            raise SAMLRelayStateError("RelayState 不存在、已过期或已被使用")
        if relay_payload.get("provider") != provider:
            raise SAMLRelayStateError(
                f"RelayState 与 provider 不匹配: expected={relay_payload['provider']} actual={provider}"
            )

        # 2. 解析并校验 SAMLResponse
        idp_cfg = self.get_provider_config(provider)
        try:
            saml_data = parse_saml_response(request_data, idp_cfg, strict=True)
        except ValueError as e:
            raise SAMLResponseError(str(e)) from e

        nameid = saml_data["nameid"]
        issuer = saml_data["issuer"]
        session_index = saml_data.get("session_index") or ""
        attributes = saml_data.get("attributes", {})
        if not nameid:
            raise SAMLResponseError("SAMLResponse 缺少 NameID")

        # 3. 用户映射 / 自动配置
        try:
            user = await self._provisioner.provision(
                db, provider, issuer, nameid, attributes
            )
        except ValueError as e:
            raise SAMLUserNotBoundError(str(e)) from e

        # 持久化 SessionIndex 供后续 SLO 使用
        user.saml_session_index = session_index
        user.last_login_time = utcnow()
        user.login_count = (user.login_count or 0) + 1
        await db.commit()
        await db.refresh(user)

        # 4. 签发本平台 token + 创建会话
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.SAML_ACCESS_TOKEN_TTL_MINUTES),
        )
        refresh_token, refresh_jti = create_refresh_token_with_jti(data=token_data)

        from app.services.session_service import SessionService
        session_service = SessionService(db)
        refresh_expires_at = utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        await session_service.create_session(
            user_id=user.id,
            refresh_jti=refresh_jti,
            expires_at=refresh_expires_at,
            user_agent=f"SAML/{provider}",
            ip_address=None,
        )
        logger.info(f"SAML 登录成功: provider={provider} user_id={user.id}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "saml_provider": provider,
            },
        }

    # ── SLO（Single Logout）──

    def build_logout_redirect(
        self,
        provider: str,
        name_id: str,
        session_index: str,
        request_data: Optional[Dict[str, Any]] = None,
        relay_state: str = "",
    ) -> str:
        """构造 SAML LogoutRequest 跳转 URL（SP 发起 SLO）。"""
        idp_cfg = self.get_provider_config(provider)
        if request_data is None:
            request_data = self._build_minimal_request_data(settings.SAML_SP_SLO_URL)
        return build_logout_request_redirect(
            request_data, idp_cfg, name_id, session_index, relay_state, strict=True
        )

    def handle_slo(
        self,
        provider: str,
        request_data: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """处理 IdP 发起的 SLO（解析 LogoutResponse）。"""
        idp_cfg = self.get_provider_config(provider)
        return parse_logout_response(request_data, idp_cfg, strict=True)

    # ── 元数据端点 ──

    def get_provider_metadata(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """获取 IdP 元数据（供前端展示已配置的 IdP 列表 / 单个详情）。"""
        if provider is not None:
            cfg = self.get_provider_config(provider)
            return {
                "provider": cfg["provider"],
                "entity_id": cfg.get("entity_id", ""),
                "sso_url": cfg.get("sso_url", ""),
                "slo_url": cfg.get("slo_url", ""),
                "nameid_format": cfg.get(
                    "nameid_format",
                    "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
                ),
            }
        providers = [
            {
                "provider": cfg["provider"],
                "entity_id": cfg.get("entity_id", ""),
                "sso_url": cfg.get("sso_url", ""),
            }
            for cfg in settings.saml_idp_configs_list
        ]
        return {
            "providers": providers,
            "default_provider": settings.SAML_DEFAULT_PROVIDER,
        }
