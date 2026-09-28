"""用户会话治理服务（add-security-compliance Task 2）。

支撑登录/登出/刷新/会话查询的统一会话治理：
    - 登录成功后创建 UserSession 记录，绑定 refresh_token 的 jti
    - logout 撤销单个会话 + access_token jti 加入黑名单
    - logout-all 撤销用户所有有效会话
    - refresh 校验 refresh_token 未被撤销并更新 last_active_at
    - SCIM deprovisioning 时级联撤销所有会话

设计要点：
    - 会话撤销幂等：重复 logout 同一 jti 不报错
    - 黑名单写入失败仅记录日志，不阻断主流程（降级为 DB revoked_at 兜底）
    - refresh 时同时校验 DB revoked_at 与 Redis 黑名单，双重保险
"""
from datetime import timedelta
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_session import UserSession
from app.utils.db_time import utcnow
from app.utils.jwt_utils import blacklist_token


class SessionService:
    """用户会话治理服务。

    封装 UserSession 表的 CRUD 与黑名单联动，供 auth_endpoints 调用。
    """

    def __init__(self, db: AsyncSession) -> None:
        """注入数据库会话。"""
        self.db = db

    async def create_session(
        self,
        *,
        user_id: int,
        refresh_jti: str,
        expires_at,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> UserSession:
        """登录成功后创建会话记录。

        Args:
            user_id: 用户 ID
            refresh_jti: refresh_token 的 jti 声明
            expires_at: 会话过期时间（与 refresh_token exp 对齐）
            user_agent: 客户端 User-Agent
            ip_address: 登录 IP

        Returns:
            UserSession: 已创建的会话对象
        """
        session = UserSession(
            user_id=user_id,
            refresh_jti=refresh_jti,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(f"创建会话: user_id={user_id} jti={refresh_jti[:8]}...")
        return session

    async def get_session(self, session_id: int) -> Optional[UserSession]:
        """按 ID 查询单个会话记录（不修改状态）。

        供端点层在撤销前做归属校验，避免先撤销后鉴权导致的越权问题。

        Args:
            session_id: 会话 ID

        Returns:
            Optional[UserSession]: 会话对象；不存在返回 None
        """
        result = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, session_id: int) -> Optional[UserSession]:
        """撤销指定会话（写入 revoked_at）。

        幂等：已撤销的会话重复撤销不报错，返回原对象。

        Args:
            session_id: 会话 ID

        Returns:
            Optional[UserSession]: 撤销后的会话对象；不存在返回 None
        """
        result = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None
        if session.revoked_at is None:
            session.revoked_at = utcnow()
            await self.db.commit()
            await self.db.refresh(session)
            # 同步 refresh_jti 到黑名单（防止 refresh_token 仍可用）
            blacklist_token(session.refresh_jti, session.expires_at)
            logger.info(f"撤销会话: id={session_id} jti={session.refresh_jti[:8]}...")
        return session

    async def revoke_session_by_jti(self, refresh_jti: str) -> bool:
        """通过 refresh_jti 撤销会话（logout 端点使用）。

        Args:
            refresh_jti: refresh_token 的 jti

        Returns:
            bool: True 表示找到并撤销；False 表示未找到
        """
        result = await self.db.execute(
            select(UserSession).where(UserSession.refresh_jti == refresh_jti)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return False
        if session.revoked_at is None:
            session.revoked_at = utcnow()
            await self.db.commit()
            logger.info(f"按 jti 撤销会话: jti={refresh_jti[:8]}...")
        # 同步到黑名单
        blacklist_token(refresh_jti, session.expires_at)
        return True

    async def revoke_all_user_sessions(self, user_id: int) -> int:
        """撤销用户所有有效会话（logout-all 与 SCIM deprovisioning 使用）。

        Args:
            user_id: 用户 ID

        Returns:
            int: 撤销的会话数
        """
        # 先查询所有有效会话（需要 jti 加入黑名单）
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
        )
        sessions = result.scalars().all()
        if not sessions:
            return 0

        now = utcnow()
        # 批量更新 revoked_at
        await self.db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self.db.commit()

        # 同步所有 jti 到黑名单
        for session in sessions:
            blacklist_token(session.refresh_jti, session.expires_at)

        logger.info(f"撤销用户 {user_id} 的 {len(sessions)} 个会话")
        return len(sessions)

    async def get_user_sessions(
        self, user_id: int, include_revoked: bool = False
    ) -> List[UserSession]:
        """查询用户会话列表。

        Args:
            user_id: 用户 ID
            include_revoked: 是否包含已撤销的会话

        Returns:
            List[UserSession]: 会话列表（按创建时间倒序）
        """
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        if not include_revoked:
            stmt = stmt.where(UserSession.revoked_at.is_(None))
        stmt = stmt.order_by(UserSession.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_session_by_jti(self, refresh_jti: str) -> Optional[UserSession]:
        """通过 refresh_jti 查询会话（refresh 端点校验使用）。

        Args:
            refresh_jti: refresh_token 的 jti

        Returns:
            Optional[UserSession]: 会话对象；不存在返回 None
        """
        result = await self.db.execute(
            select(UserSession).where(UserSession.refresh_jti == refresh_jti)
        )
        return result.scalar_one_or_none()

    async def touch_session(self, refresh_jti: str) -> None:
        """更新会话最后活跃时间（refresh 端点调用）。

        Args:
            refresh_jti: refresh_token 的 jti
        """
        await self.db.execute(
            update(UserSession)
            .where(UserSession.refresh_jti == refresh_jti)
            .values(last_active_at=utcnow())
        )
        await self.db.commit()
