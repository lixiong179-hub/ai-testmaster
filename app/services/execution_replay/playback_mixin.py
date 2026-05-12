"""回放控制Mixin - 控制执行过程的回放（播放/暂停/跳转/调速）。
"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger


class PlaybackMixin:

    async def start_replay(
        self,
        session_id: str,
        speed: Optional[float] = None,
        start_from: int = 0
    ) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        if session.is_playing:
            return {"status": "already_playing", "session": session.to_dict()}

        session.speed = speed or self._default_speed
        session.current_event_index = start_from
        session.is_playing = True
        session.is_paused = False
        self._update_activity(session_id)

        asyncio.create_task(self._replay_loop(session_id))

        logger.info(f"开始回放: session={session_id}, speed={session.speed}x, from={start_from}")
        return {"status": "started", "session": session.to_dict()}

    async def _replay_loop(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        try:
            while session.is_playing and session.current_event_index < len(session.timeline.events):
                if session.is_paused:
                    await asyncio.sleep(0.1)
                    continue

                event = session.timeline.events[session.current_event_index]

                if self._event_callback:
                    try:
                        self._event_callback(session_id, event)
                    except Exception as e:
                        logger.warning(f"事件回调失败: {e}")

                delay = max(event.duration_ms, 500) / 1000.0 / session.speed
                await asyncio.sleep(delay)

                session.current_event_index += 1
                self._update_activity(session_id)

            session.is_playing = False
            logger.info(f"回放完成: session={session_id}")

        except asyncio.CancelledError:
            session.is_playing = False
            logger.info(f"回放被取消: session={session_id}")
        except Exception as e:
            session.is_playing = False
            logger.error(f"回放异常: session={session_id}, error={e}")

    async def pause_replay(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        if not session.is_playing:
            return {"status": "not_playing", "session": session.to_dict()}

        session.is_paused = True
        self._update_activity(session_id)

        logger.info(f"暂停回放: session={session_id}")
        return {"status": "paused", "session": session.to_dict()}

    async def resume_replay(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        if not session.is_paused:
            return {"status": "not_paused", "session": session.to_dict()}

        session.is_paused = False
        self._update_activity(session_id)

        logger.info(f"恢复回放: session={session_id}")
        return {"status": "resumed", "session": session.to_dict()}

    async def stop_replay(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        session.is_playing = False
        session.is_paused = False
        self._update_activity(session_id)

        logger.info(f"停止回放: session={session_id}")
        return {"status": "stopped", "session": session.to_dict()}

    async def seek_to(self, session_id: str, event_index: int) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        if event_index < 0 or event_index >= len(session.timeline.events):
            raise ValueError(f"无效的事件索引: {event_index}")

        session.current_event_index = event_index
        self._update_activity(session_id)

        logger.info(f"跳转到事件 {event_index}: session={session_id}")
        return {"status": "seeked", "current_index": event_index, "session": session.to_dict()}

    async def get_replay_status(self, session_id: str) -> Dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"回放会话不存在: {session_id}")

        return {
            "session_id": session_id,
            "is_playing": session.is_playing,
            "is_paused": session.is_paused,
            "current_event_index": session.current_event_index,
            "total_events": len(session.timeline.events),
            "speed": session.speed,
            "progress": session.current_event_index / max(len(session.timeline.events), 1) * 100,
        }
