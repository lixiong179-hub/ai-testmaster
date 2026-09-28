"""OIDC token 换取与 id_token 解析 mixin（从 oidc_service.py 拆出）。"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from loguru import logger

from app.core.config import settings
from app.services.oidc_exceptions import (
    OIDCServiceError,
    OIDCStateError,
    OIDCTokenError,
)


class OIDCTokenMixin:
    """授权码换 token、id_token 解析与验签。

    依赖宿主类提供的方法：_consume_state / get_provider_config / _derive_token_endpoint。
    """

    async def exchange_code_for_tokens(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """用授权码换取 IdP 的 access_token / id_token。

        Args:
            provider: IdP 标识
            code: 授权码
            state: state 参数（用于校验 + 获取 redirect_uri）

        Returns:
            dict: IdP 返回的 token 响应，含 access_token/id_token/expires_in 等

        Raises:
            OIDCStateError: state 校验失败
            OIDCTokenError: token 端点请求失败
        """
        # 先消费 state（一次性）
        state_payload = self._consume_state(state)
        if state_payload is None:
            raise OIDCStateError("state 不存在、已过期或已被使用")
        if state_payload.get("provider") != provider:
            raise OIDCStateError(f"state 与 provider 不匹配: expected={state_payload['provider']} actual={provider}")

        cfg = self.get_provider_config(provider)
        token_endpoint = self._derive_token_endpoint(cfg)

        try:
            from authlib.integrations.httpx_client import AsyncOAuth2Client
        except ImportError as e:
            raise OIDCServiceError(f"authlib 未安装: {e}") from e

        try:
            async with AsyncOAuth2Client(
                client_id=cfg["client_id"],
                client_secret=cfg["client_secret"],
                redirect_uri=cfg["redirect_uri"],
                state=state,
            ) as client:
                token_response = await client.fetch_token(
                    token_endpoint,
                    authorization_response=f"?code={code}&state={state}",
                    code=code,
                    grant_type="authorization_code",
                )
                return dict(token_response)
        except Exception as e:
            logger.error(f"OIDC token 换取失败: provider={provider} error={e}")
            raise OIDCTokenError(f"授权码换取 token 失败: {e}") from e

    def parse_id_token(
        self,
        provider: str,
        id_token: str,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """解析并验证 id_token，返回 claims。

        Args:
            provider: IdP 标识
            id_token: IdP 签发的 id_token JWT
            nonce: 期望的 nonce 值（防止重放攻击）

        Returns:
            dict: id_token 的 claims（含 sub/email/name/picture 等）

        Raises:
            OIDCTokenError: 解析失败或 nonce 校验失败
        """
        cfg = self.get_provider_config(provider)
        issuer = cfg.get("issuer", "")
        client_id = cfg["client_id"]

        try:
            from authlib.jose import jwt as jose_jwt
            from authlib.oidc.core import IDToken
        except ImportError as e:
            raise OIDCServiceError(f"authlib 未安装: {e}") from e

        # IdP 的 JWKS 公钥（用于验签）
        # 生产环境应从 IdP 的 jwks_uri 获取并缓存；
        # 此处通过 authlib 的 AsyncOAuth2Client.fetch_jwks 获取或直接配置 jwks
        jwks = cfg.get("jwks")
        is_authlib_claims = False
        try:
            if jwks:
                claims = jose_jwt.decode(
                    id_token,
                    jwks,
                    claims_cls=IDToken,
                    claims_options={
                        "iss": {"value": issuer} if issuer else None,
                        "aud": {"value": client_id},
                    },
                )
                is_authlib_claims = True
            else:
                # 未配置 jwks：生产环境强制拒绝（防止伪造 id_token），仅开发环境降级跳过验签
                if settings.ENVIRONMENT == "prod":
                    raise OIDCTokenError(
                        f"OIDC IdP {provider} 未配置 jwks，生产环境禁止跳过 id_token 验签"
                    )
                logger.warning(
                    f"OIDC IdP {provider} 未配置 jwks，跳过 id_token 验签（仅限开发环境）"
                )
                # 手动解析 JWT payload（不验签），避免依赖 PyJWT
                # 标准 JWT 格式：header.payload.signature，payload 为 base64url 编码的 JSON
                claims = self._decode_jwt_payload_unverified(id_token)
                # 手动校验 iss / aud（跳过签名时不校验这些）
                if issuer and claims.get("iss") != issuer:
                    raise OIDCTokenError(
                        f"id_token iss 校验失败: expected={issuer} actual={claims.get('iss')}"
                    )
                if claims.get("aud") != client_id:
                    raise OIDCTokenError(
                        f"id_token aud 校验失败: expected={client_id} actual={claims.get('aud')}"
                    )
        except OIDCTokenError:
            raise
        except Exception as e:
            logger.error(f"OIDC id_token 解析失败: provider={provider} error={e}")
            raise OIDCTokenError(f"id_token 解析失败: {e}") from e

        # nonce 校验（防止重放攻击）
        if nonce and claims.get("nonce") and claims["nonce"] != nonce:
            raise OIDCTokenError("id_token nonce 校验失败（疑似重放攻击）")

        # authlib IDToken claims 对象需调用 validate() 校验 exp/iat/nbf 等标准声明
        # pyjwt 返回的 plain dict 已在上方手动校验 iss/aud，无需调用 validate()
        if is_authlib_claims:
            try:
                claims.validate()
            except Exception as e:
                raise OIDCTokenError(f"id_token 标准声明校验失败: {e}") from e
        return dict(claims)

    def _decode_jwt_payload_unverified(self, id_token: str) -> Dict[str, Any]:
        """解析 JWT 的 payload 部分但不验签（仅用于开发/测试环境）。

        标准 JWT 格式：header.payload.signature
        payload 为 base64url 编码的 JSON。

        Args:
            id_token: JWT 字符串

        Returns:
            dict: payload 字典

        Raises:
            OIDCTokenError: 格式错误或解析失败
        """
        import base64
        import json as _json

        parts = id_token.split(".")
        if len(parts) != 3:
            raise OIDCTokenError("id_token 格式错误：应为三段式 JWT")
        try:
            # base64url 解码（补齐 padding）
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            return _json.loads(payload_bytes)
        except Exception as e:
            raise OIDCTokenError(f"id_token payload 解析失败: {e}") from e


__all__ = ["OIDCTokenMixin"]
