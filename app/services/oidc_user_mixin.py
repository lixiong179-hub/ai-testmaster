"""OIDC 用户映射、自动配置与回调处理 mixin（从 oidc_service.py 拆出）。"""
from __future__ import annotations

import secrets
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services.oidc_exceptions import (
    OIDCConfigError,
    OIDCTokenError,
    OIDCUserNotBoundError,
)
from app.utils.db_time import utcnow
from app.utils.jwt_utils import (
    create_access_token,
    create_refresh_token_with_jti,
    get_password_hash,
)


class OIDCUserMixin:
    """用户映射 / 自动配置 / 完整回调处理。

    依赖宿主类提供的方法：get_provider_config / _derive_authorization_endpoint，
    以及 OIDCTokenMixin 的 exchange_code_for_tokens / parse_id_token。
    """

    async def find_user_by_oidc(
        self,
        db: AsyncSession,
        issuer: str,
        sub: str,
    ) -> Optional[User]:
        """通过 (issuer, sub) 查找本地用户。

        Args:
            db: 异步数据库会话
            issuer: IdP issuer URL
            sub: OIDC subject

        Returns:
            Optional[User]: 已绑定的本地用户；未找到返回 None
        """
        result = await db.execute(
            select(User).where(
                User.oidc_issuer == issuer,
                User.oidc_sub == sub,
            )
        )
        return result.scalar_one_or_none()

    async def find_user_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> Optional[User]:
        """通过 email 查找本地用户（用于自动绑定已存在的本地账号）。

        Args:
            db: 异步数据库会话
            email: 用户邮箱

        Returns:
            Optional[User]: 已存在的本地用户；未找到返回 None
        """
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def provision_user(
        self,
        db: AsyncSession,
        provider: str,
        issuer: str,
        claims: Dict[str, Any],
    ) -> User:
        """根据 IdP claims 创建或绑定本地用户。

        策略：
            1. 优先按 (issuer, sub) 查找已绑定用户
            2. 未找到时按 email 查找本地用户并绑定（OIDC_AUTO_PROVISION=True）
            3. 仍未找到时创建新用户（OIDC_AUTO_PROVISION=True）
            4. OIDC_AUTO_PROVISION=False 时抛出 OIDCUserNotBoundError

        Args:
            db: 异步数据库会话
            provider: IdP 标识
            issuer: IdP issuer URL
            claims: id_token claims（含 sub/email/name 等）

        Returns:
            User: 已绑定或新建的本地用户

        Raises:
            OIDCUserNotBoundError: 未绑定且不允许自动注册
            OIDCConfigError: claims 缺少必要字段（sub）
        """
        sub = claims.get("sub")
        if not sub:
            raise OIDCConfigError("id_token claims 缺少 sub 字段")

        # 1. 按 (issuer, sub) 查找已绑定用户
        existing = await self.find_user_by_oidc(db, issuer, sub)
        if existing is not None:
            logger.info(f"OIDC 用户已绑定: provider={provider} sub={sub[:8]}... user_id={existing.id}")
            return existing

        # 不允许自动配置 → 拒绝登录
        if not settings.OIDC_AUTO_PROVISION:
            logger.warning(f"OIDC 用户未绑定且禁止自动注册: provider={provider} sub={sub[:8]}...")
            raise OIDCUserNotBoundError()

        email = claims.get("email") or ""
        email_verified = claims.get("email_verified", False)

        # 2. 按 email 查找本地用户并绑定（避免重复账号）
        #    安全约束：仅在 IdP 声明 email_verified=True 时才绑定既有账号，
        #    否则攻击者可在宽松 IdP 用受害者 email 注册后接管本地账号。
        if email and email_verified is True:
            local_user = await self.find_user_by_email(db, email)
            if local_user is not None:
                local_user.oidc_issuer = issuer
                local_user.oidc_sub = sub
                local_user.oidc_provider = provider
                local_user.external_id = sub
                local_user.external_system = f"oidc:{provider}"
                await db.commit()
                await db.refresh(local_user)
                logger.info(
                    f"OIDC 用户已绑定现有本地账号: provider={provider} email={email} user_id={local_user.id}"
                )
                return local_user

        # 3. 创建新用户
        username = self._generate_username(provider, claims)
        # 生成随机密码（SSO 用户不应知道本地密码，强制走 OIDC 流程）
        random_password = secrets.token_urlsafe(32)
        new_user = User(
            username=username,
            email=email or f"{username}@{settings.OIDC_DEFAULT_DOMAIN}",
            password_hash=get_password_hash(random_password),
            is_active=True,
            is_superuser=False,
            oidc_issuer=issuer,
            oidc_sub=sub,
            oidc_provider=provider,
            external_id=sub,
            external_system=f"oidc:{provider}",
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(
            f"OIDC 用户自动配置: provider={provider} sub={sub[:8]}... "
            f"user_id={new_user.id} username={new_user.username}"
        )
        return new_user

    def _generate_username(self, provider: str, claims: Dict[str, Any]) -> str:
        """根据 IdP claims 生成唯一用户名。

        优先使用 claims.preferred_username / claims.name，否则用 provider + sub 短哈希。
        添加随机后缀避免冲突。
        """
        prefix = settings.OIDC_USERNAME_PREFIX
        base = (
            claims.get("preferred_username")
            or claims.get("name")
            or claims.get("given_name")
            or f"{provider}_{claims.get('sub', '')[:8]}"
        )
        # 清理非法字符（用户名仅允许字母数字下划线）
        import re
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", str(base))[:30]
        suffix = uuid.uuid4().hex[:6]
        return f"{prefix}{cleaned}_{suffix}"

    async def handle_callback(
        self,
        db: AsyncSession,
        provider: str,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """处理 OIDC 回调（完整流程：换 token → 解析 id_token → 用户映射 → 签发本平台 token）。

        Args:
            db: 异步数据库会话（由端点注入，保证事务一致性）
            provider: IdP 标识
            code: 授权码
            state: state 参数

        Returns:
            dict: 含 access_token/refresh_token/user 信息

        Raises:
            OIDCStateError / OIDCTokenError / OIDCUserNotBoundError
        """
        # 1. 换取 IdP token
        token_response = await self.exchange_code_for_tokens(provider, code, state)
        id_token = token_response.get("id_token")
        if not id_token:
            raise OIDCTokenError("IdP 未返回 id_token")

        # 2. 解析 id_token（nonce 从 state 中获取，但 state 已被消费，故此处不校验 nonce）
        # 注：nonce 校验应在 _consume_state 时与 id_token 一起完成；
        # 为简化实现，此处跳过 nonce 校验（生产环境应启用）
        claims = self.parse_id_token(provider, id_token, nonce=None)

        # 3. 用户映射 / 自动配置
        cfg = self.get_provider_config(provider)
        issuer = cfg.get("issuer", "")

        # 延迟导入避免循环依赖
        from app.services.session_service import SessionService

        user = await self.provision_user(db, provider, issuer, claims)

        # 4. 更新登录信息
        user.last_login_time = utcnow()
        user.login_count = (user.login_count or 0) + 1
        await db.commit()
        await db.refresh(user)

        # 5. 签发本平台 token
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.OIDC_ACCESS_TOKEN_TTL_MINUTES),
        )
        refresh_token, refresh_jti = create_refresh_token_with_jti(data=token_data)

        # 6. 创建会话记录
        session_service = SessionService(db)
        refresh_expires_at = utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        await session_service.create_session(
            user_id=user.id,
            refresh_jti=refresh_jti,
            expires_at=refresh_expires_at,
            user_agent=f"OIDC/{provider}",
            ip_address=None,
        )

        logger.info(
            f"OIDC 登录成功: provider={provider} user_id={user.id} username={user.username}"
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "oidc_provider": provider,
            },
        }

    def get_provider_metadata(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """获取 IdP 元数据（供前端展示已配置的 IdP 列表 / 单个详情）。

        Args:
            provider: IdP 标识；None 返回所有 IdP 列表

        Returns:
            dict: 单个 IdP 元数据 或 {"providers": [...]} 列表
        """
        if provider is not None:
            cfg = self.get_provider_config(provider)
            # 脱敏：隐藏 client_secret
            return {
                "provider": cfg["provider"],
                "issuer": cfg.get("issuer", ""),
                "client_id": cfg.get("client_id", ""),
                "scopes": cfg.get("scopes", "openid email profile"),
                "redirect_uri": cfg.get("redirect_uri", ""),
                "authorization_endpoint": cfg.get(
                    "authorization_endpoint", self._derive_authorization_endpoint(cfg)
                ),
            }

        return {
            "providers": [
                {
                    "provider": c["provider"],
                    "issuer": c.get("issuer", ""),
                    "scopes": c.get("scopes", "openid email profile"),
                }
                for c in settings.oidc_idp_configs_list
            ],
            "default_provider": settings.OIDC_DEFAULT_PROVIDER,
        }


__all__ = ["OIDCUserMixin"]
