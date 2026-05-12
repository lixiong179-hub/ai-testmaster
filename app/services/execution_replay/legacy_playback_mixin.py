"""Legacy 回放控制Mixin - execution_replay_service.py 原始回放控制逻辑。"""
import asyncio
from typing import Optional, Dict, Any, Callable
from loguru import logger

from app.services.execution_replay.legacy_models import ReplayEvent


class LegacyPlaybackMixin:
    """回放控制：开始、暂停、恢复、停止、跳转、调速。"""

    async def start_replay(
        self,
        execution_id: str,
        start_time: float = 0.0,
        speed: float = 1.0,
        event_callback: Optional[Callable[[ReplayEvent], None]] = None
    ) -> bool:
        session = self._active_replays.get(execution_id)
        if not session:
            logger.error(f"回放会话不存在: {execution_id}")
            return False
        if session["is_playing"]:
            logger.warning(f"回放已在进行中: {execution_id}")
            return False
        session["is_playing"] = True
        session["current_time"] = start_time
        session["speed"] = speed
        logger.info(f"开始回放: {execution_id}, 速度={speed}x, 起始时间={start_time}s")
        asyncio.create_task(self._replay_loop(execution_id, event_callback))
        return True

    async def _replay_loop(
        self,
        execution_id: str,
        event_callback: Optional[Callable[[ReplayEvent], None]] = None
    ):
        session = self._active_replays.get(execution_id)
        if not session:
            return
        timeline = session["timeline"]
        speed = session["speed"]
        current_idx = 0
        while current_idx < len(timeline.events):
            if timeline.events[current_idx].timestamp >= session["current_time"]:
                break
            current_idx += 1
        last_event_time = session["current_time"]
        while session["is_playing"] and current_idx < len(timeline.events):
            event = timeline.events[current_idx]
            wait_time = (event.timestamp - last_event_time) / speed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            session["current_time"] = event.timestamp
            last_event_time = event.timestamp
            if event_callback:
                try:
                    event_callback(event)
                except Exception as e:
                    logger.error(f"事件回调失败: {e}")
            current_idx += 1
        session["is_playing"] = False
        logger.info(f"回放结束: {execution_id}")

    async def pause_replay(self, execution_id: str) -> bool:
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        session["is_playing"] = False
        logger.info(f"回放已暂停: {execution_id}, 当前时间={session['current_time']}s")
        return True

    async def resume_replay(self, execution_id: str) -> bool:
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        if session["is_playing"]:
            return True
        session["is_playing"] = True
        logger.info(f"回放已恢复: {execution_id}")
        return True

    async def stop_replay(self, execution_id: str) -> bool:
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        session["is_playing"] = False
        session["current_time"] = 0.0
        logger.info(f"回放已停止: {execution_id}")
        return True

    async def seek_to(self, execution_id: str, timestamp: float) -> bool:
        session = self._active_replays.get(execution_id)
        if not session:
            return False
        timeline = session["timeline"]
        if timestamp < 0:
            timestamp = 0
        if timestamp > timeline.total_duration:
            timestamp = timeline.total_duration
        session["current_time"] = timestamp
        logger.info(f"回放跳转: {execution_id} -> {timestamp}s")
        return True

    async def get_replay_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        session = self._active_replays.get(execution_id)
        if not session:
            return None
        timeline = session["timeline"]
        current_event_idx = 0
        for i, event in enumerate(timeline.events):
            if event.timestamp > session["current_time"]:
                break
            current_event_idx = i
        return {
            "execution_id": execution_id,
            "is_playing": session["is_playing"],
            "current_time": session["current_time"],
            "total_duration": timeline.total_duration,
            "progress_percent": (session["current_time"] / timeline.total_duration * 100) if timeline.total_duration > 0 else 0,
            "speed": session["speed"],
            "current_event_index": current_event_idx,
            "total_events": len(timeline.events)
        }

    def set_default_speed(self, speed: float) -> None:
        if speed < 0.1:
            speed = 0.1
        if speed > 10.0:
            speed = 10.0
        self._replay_speed = speed
        logger.info(f"默认回放速度已设置为: {speed}x")
