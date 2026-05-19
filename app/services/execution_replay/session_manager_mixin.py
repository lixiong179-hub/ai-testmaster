"""会话管理Mixin - 管理回放会话的创建、销毁和超时清理。
"""
import asyncio
import uuid
from datetime import datetime
from loguru import logger

from app.services.execution_replay.models import ReplaySession
from app.utils.db_time import utcnow


class SessionManagerMixin:

    async def create_replay_session(self, execution_id: int) -> str:
        timeline = await self._load_execution_timeline(execution_id)
        if not timeline:
            raise ValueError(f"执行记录不存在: {execution_id}")

        session_id = str(uuid.uuid4())
        session = ReplaySession(
            session_id=session_id,
            execution_id=execution_id,
            timeline=timeline,
        )

        self._sessions[session_id] = session
        self._update_activity(session_id)

        logger.info(f"创建回放会话: {session_id}, 执行ID: {execution_id}")
        return session_id

    async def close_replay_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            if session.is_playing:
                session.is_playing = False
                session.is_paused = False
            del self._sessions[session_id]
            logger.info(f"关闭回放会话: {session_id}")

    def _start_cleanup_task(self) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._cleanup_expired_sessions())
        except RuntimeError:
            logger.debug("获取事件循环失败，跳过清理任务启动")

    async def _cleanup_expired_sessions(self) -> None:
        while True:
            try:
                await asyncio.sleep(300)
                self._remove_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理过期会话失败: {e}")

    def _remove_expired_sessions(self) -> None:
        now = utcnow()
        expired_ids = []

        for session_id, session in self._sessions.items():
            idle_time = (now - session.last_activity).total_seconds()
            if idle_time > self._session_timeout:
                expired_ids.append(session_id)

        for session_id in expired_ids:
            session = self._sessions.get(session_id)
            if session and session.is_playing:
                session.is_playing = False
            del self._sessions[session_id]
            logger.info(f"清理过期回放会话: {session_id}")

    def _update_activity(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.last_activity = utcnow()

    def set_default_speed(self, speed: float) -> None:
        if 0.25 <= speed <= 4.0:
            self._default_speed = speed
            logger.info(f"默认回放速度设置为: {speed}x")
        else:
            logger.warning(f"无效的回放速度: {speed}, 有效范围: 0.25-4.0")
