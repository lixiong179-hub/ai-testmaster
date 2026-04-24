"""Legacy 数据模型 - execution_replay_service.py 原始数据模型定义。"""
from typing import Optional, List, Dict, Any, TypedDict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReplayEvent:
    """回放事件"""
    timestamp: float
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "data": self.data
        }


@dataclass
class ExecutionTimeline:
    """执行时间轴"""
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0
    events: List[ReplayEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration": self.total_duration,
            "events": [e.to_dict() for e in self.events]
        }


class ReplaySession(TypedDict):
    """回放会话类型定义"""
    execution_id: str
    timeline: ExecutionTimeline
    video_path: Optional[str]
    screenshots: List[str]
    current_time: float
    is_playing: bool
    speed: float
    created_at: datetime
    last_activity: datetime
