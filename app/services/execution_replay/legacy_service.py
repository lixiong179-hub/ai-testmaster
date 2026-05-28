"""Legacy 执行回放服务 - 兼容原始 execution_replay_service.py 的完整实现。

所有逻辑已拆分为独立Mixin，本文件仅做最终组合并提供全局单例函数。
"""
from typing import Any, Dict, Optional

from app.services.execution_replay.legacy_models import (
    ReplayEvent, ExecutionTimeline, ReplaySession
)
from app.services.execution_replay.legacy_session_mixin import LegacySessionMixin
from app.services.execution_replay.legacy_playback_mixin import LegacyPlaybackMixin
from app.services.execution_replay.legacy_query_mixin import LegacyQueryMixin


class ExecutionReplayService(LegacySessionMixin, LegacyPlaybackMixin, LegacyQueryMixin):
    """执行回放服务（Legacy兼容版）"""

    def __init__(self):
        super().__init__()
        self._start_cleanup_task()

    async def get_session(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取指定执行回放会话的可序列化快照。"""
        session = self._active_replays.get(execution_id)
        if not session:
            return None

        self._update_activity(execution_id)

        timeline = session.get("timeline")
        created_at = session.get("created_at")
        last_activity = session.get("last_activity")

        return {
            "execution_id": session.get("execution_id"),
            "timeline": timeline.to_dict() if timeline else None,
            "video_path": session.get("video_path"),
            "screenshots": session.get("screenshots", []),
            "current_time": session.get("current_time", 0.0),
            "is_playing": session.get("is_playing", False),
            "speed": session.get("speed", self._replay_speed),
            "created_at": created_at.isoformat() if created_at else None,
            "last_activity": last_activity.isoformat() if last_activity else None,
        }

    async def set_speed(self, execution_id: str, speed: float) -> bool:
        """设置指定回放会话的速度；无会话时更新默认速度。"""
        if speed < 0.1:
            speed = 0.1
        if speed > 10.0:
            speed = 10.0

        session = self._active_replays.get(execution_id)
        if not session:
            self.set_default_speed(speed)
            return False

        session["speed"] = speed
        self._update_activity(execution_id)
        return True


_execution_replay_service = None


def get_execution_replay_service() -> ExecutionReplayService:
    """获取执行回放服务实例（单例）"""
    global _execution_replay_service
    if _execution_replay_service is None:
        _execution_replay_service = ExecutionReplayService()
    return _execution_replay_service


__all__ = [
    "ExecutionReplayService",
    "get_execution_replay_service",
    "ReplayEvent",
    "ExecutionTimeline",
    "ReplaySession",
]
