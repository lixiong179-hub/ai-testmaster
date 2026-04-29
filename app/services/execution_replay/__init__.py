"""执行回放子包 - 通过Mixin组合模式实现测试执行过程的录制与回放。

本子包是执行回放服务的核心实现，ExecutionReplayService通过多继承
组合各功能Mixin，实现执行过程的录制、时间线构建、回放控制和查询。

核心类:
    - ExecutionReplayService: 执行回放服务主类（单例模式）

Mixin组合:
    - QueryMixin: 回放数据查询
    - PlaybackMixin: 回放控制（播放/暂停/跳转/调速）
    - TimelineMixin: 时间线构建
    - SessionManagerMixin: 会话管理（创建/销毁/超时清理）

回放流程:
    1. 执行过程中录制事件（截图/操作/状态变更）
    2. 构建执行时间线
    3. 创建回放会话
    4. 支持播放/暂停/跳转/调速
    5. 会话超时自动清理
"""
from typing import Optional, Dict, Any, Callable
from sqlalchemy.orm import Session

from app.services.execution_replay.models import (
    ReplayEvent, ReplayEventType, ExecutionTimeline, ReplaySession,
)
from app.services.execution_replay.session_manager_mixin import SessionManagerMixin
from app.services.execution_replay.timeline_mixin import TimelineMixin
from app.services.execution_replay.playback_mixin import PlaybackMixin
from app.services.execution_replay.query_mixin import QueryMixin


class ExecutionReplayService(
    SessionManagerMixin,
    TimelineMixin,
    PlaybackMixin,
    QueryMixin,
):
    """执行回放服务 - 组合会话管理/时间线/回放/查询四个Mixin。

    采用单例模式，确保全局只有一个回放服务实例。

    使用场景:
        - 测试执行过程的实时录制
        - 执行结果的时间线回放
        - 失败步骤的调试回放
    """

    _instance = None

    def __init__(
        self,
        db: Session,
        session_timeout: int = 1800,
        default_speed: float = 1.0,
        event_callback: Optional[Callable] = None,
    ):
        """初始化执行回放服务。

        Args:
            db: 数据库会话。
            session_timeout: 会话超时时间（秒），默认1800（30分钟）。
            default_speed: 默认回放速度，默认1.0（正常速度）。
            event_callback: 事件回调函数，可选。
        """
        self.db = db
        self._sessions: Dict[str, ReplaySession] = {}  # 会话缓存
        self._session_timeout = session_timeout
        self._default_speed = default_speed
        self._event_callback = event_callback
        self._screenshot_base_dir = '/tmp/test_screenshots'

    @classmethod
    def get_instance(cls, db: Session, **kwargs) -> 'ExecutionReplayService':
        """获取单例实例，首次调用时初始化，后续调用更新db。

        Args:
            db: 数据库会话。
            **kwargs: 初始化参数。

        Returns:
            ExecutionReplayService单例实例。
        """
        if cls._instance is None:
            cls._instance = cls(db, **kwargs)
        else:
            cls._instance.db = db
        return cls._instance


__all__ = [
    'ExecutionReplayService',
    'ReplayEvent',
    'ReplayEventType',
    'ExecutionTimeline',
    'ReplaySession',
    'SessionManagerMixin',
    'TimelineMixin',
    'PlaybackMixin',
    'QueryMixin',
]
