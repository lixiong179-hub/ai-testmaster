"""Legacy 执行回放服务 - 兼容原始 execution_replay_service.py 的完整实现。

所有逻辑已拆分为独立Mixin，本文件仅做最终组合并提供全局单例函数。
"""
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
