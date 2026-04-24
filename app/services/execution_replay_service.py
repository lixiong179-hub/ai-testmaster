"""
执行回放服务 - 兼容代理模块

所有实现已迁移到 execution_replay/legacy_service.py，本文件仅保留向后兼容的导入。
"""
from app.services.execution_replay.legacy_service import (
    ExecutionReplayService,
    get_execution_replay_service,
    ReplayEvent,
    ExecutionTimeline,
    ReplaySession,
)

__all__ = [
    "ExecutionReplayService",
    "get_execution_replay_service",
    "ReplayEvent",
    "ExecutionTimeline",
    "ReplaySession",
]
