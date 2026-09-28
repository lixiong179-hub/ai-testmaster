"""SAML 用户配置（provisioning）逻辑。

封装 SAML 登录后的用户映射与自动配置：
    1. 按 (issuer, nameid) 查找已绑定用户
    2. 按 email 查找本地用户并绑定（SAML_AUTO_PROVISION=True）
    3. 创建新用户（SAML_AUTO_PROVISION=True）

设计要点：
    - 兼容 Okta/Azure AD/ADFS 常见属性名（email/Email/mail/username/displayname）
    - NameID 为 emailaddress 格式时作为邮箱回退
    - 新用户生成随机密码（强制走 SAML 流程，不可本地登录）
    - 用户名添加 saml_ 前缀 + 随机后缀避免冲突
"""
from __future__ import annotations

import re
import secrets
import uuid
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.utils.jwt_utils import get_password_hash


class SAMLUserProvisioner:
    """SAML 用户配置器。

    负责 SAML 登录后的用户查找、绑定与自动创建。

    使用示例：
        provisioner = SAMLUserProvisioner()
        user = await provisioner.provision(db, "okta", "issuer_url", "nameid", {"email": "x@y.com"})
    """

    async def find_by_saml(
        self,
        db: AsyncSession,
        issuer: str,
        nameid: str,
    ) -> Optional[User]:
        """通过 (issuer, nameid) 查找本地用户。"""
        result = await db.execute(
            select(User).where(
                User.saml_issuer == issuer,
                User.saml_nameid == nameid,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> Optional[User]:
        """通过 email 查找本地用户（用于自动绑定已存在的本地账号）。"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def provision(
        self,
        db: AsyncSession,
        provider: str,
        issuer: str,
        nameid: str,
        attributes: Dict[str, Any],
    ) -> User:
        """根据 SAML 断言创建或绑定本地用户。

        策略：
            1. 优先按 (issuer, nameid) 查找已绑定用户
            2. 未找到时按 email 查找本地用户并绑定（SAML_AUTO_PROVISION=True）
            3. 仍未找到时创建新用户（SAML_AUTO_PROVISION=True）
            4. SAML_AUTO_PROVISION=False 时抛出 ValueError

        Args:
            db: 异步数据库会话
            provider: IdP 标识
            issuer: IdP EntityID
            nameid: SAML NameID
            attributes: SAML 属性字典

        Returns:
            User: 已绑定或新建的本地用户

        Raises:
            ValueError: 未绑定且不允许自动注册
        """
        existing = await self.find_by_saml(db, issuer, nameid)
        if existing is not None:
            logger.info(f"SAML 用户已绑定: provider={provider} user_id={existing.id}")
            return existing

        if not settings.SAML_AUTO_PROVISION:
            logger.warning(f"SAML 用户未绑定且禁止自动注册: provider={provider}")
            raise ValueError("用户未绑定本地账号，请联系管理员开通")

        email = self._extract_email(attributes, nameid)
        if email:
            local_user = await self.find_by_email(db, email)
            if local_user is not None:
                local_user.saml_issuer = issuer
                local_user.saml_nameid = nameid
                local_user.saml_provider = provider
                local_user.external_id = nameid
                local_user.external_system = f"saml:{provider}"
                await db.commit()
                await db.refresh(local_user)
                logger.info(
                    f"SAML 用户已绑定现有本地账号: email={email} user_id={local_user.id}"
                )
                return local_user

        username = self._generate_username(provider, attributes, nameid)
        random_password = secrets.token_urlsafe(32)
        new_user = User(
            username=username,
            email=email or f"{username}@{settings.OIDC_DEFAULT_DOMAIN}",
            password_hash=get_password_hash(random_password),
            is_active=True,
            is_superuser=False,
            saml_issuer=issuer,
            saml_nameid=nameid,
            saml_provider=provider,
            external_id=nameid,
            external_system=f"saml:{provider}",
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"SAML 用户自动配置: provider={provider} user_id={new_user.id}")
        return new_user

    def _extract_email(self, attributes: Dict[str, Any], nameid: str) -> str:
        """从 SAML 属性中提取邮箱。

        兼容 Okta/Azure AD 常见属性名：email / Email / mail / http://schemas...emailaddress
        NameID 为 emailaddress 格式时作为回退。
        """
        for key in ("email", "Email", "mail", "Mail"):
            val = attributes.get(key)
            if val and isinstance(val, str) and "@" in val:
                return val
        # OASIS 标准属性名（http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress）
        for key, val in attributes.items():
            if "emailaddress" in key.lower() and val and isinstance(val, str):
                return val
        # NameID 本身可能是邮箱（emailaddress 格式）
        if nameid and "@" in nameid:
            return nameid
        return ""

    def _generate_username(
        self, provider: str, attributes: Dict[str, Any], nameid: str
    ) -> str:
        """根据 SAML 属性生成唯一用户名。

        优先使用 username / displayname，否则用 nameid 本地部分。
        添加 saml_ 前缀 + 随机后缀避免冲突。
        """
        prefix = settings.SAML_USERNAME_PREFIX
        base = (
            attributes.get("username")
            or attributes.get("Username")
            or attributes.get("displayname")
            or attributes.get("DisplayName")
            or (nameid.split("@")[0] if nameid else "")
            or f"{provider}_{nameid[:8] if nameid else 'unknown'}"
        )
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", str(base))[:30]
        suffix = uuid.uuid4().hex[:6]
        return f"{prefix}{cleaned}_{suffix}"
