"""数据模型定义 - 定义本子包所需的数据结构、枚举和结果模型。
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ReplayEventType(str, Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    INPUT = "input"
    VERIFY = "verify"
    WAIT = "wait"
    SCROLL = "scroll"
    HOVER = "hover"
    SELECT = "select"
    SCREENSHOT = "screenshot"
    ERROR = "error"


class SessionStatus(str, Enum):
    """兼容旧测试导出的回放会话状态枚举。"""

    PENDING = "pending"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"


class ActionType(str, Enum):
    """兼容旧测试导出的动作类型枚举。"""

    CLICK = "click"
    INPUT = "input"
    SCROLL = "scroll"
    NAVIGATE = "navigate"


@dataclass
class ReplayEvent:
    timestamp: float
    event_type: ReplayEventType
    action: str
    step_number: int
    screenshot_path: Optional[str] = None
    element_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "action": self.action,
            "step_number": self.step_number,
            "screenshot_path": self.screenshot_path,
            "element_info": self.element_info,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ExecutionTimeline:
    execution_id: int
    test_case_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    events: List[ReplayEvent] = field(default_factory=list)
    total_duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "test_case_id": self.test_case_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class ReplaySession:
    session_id: str
    execution_id: int
    timeline: ExecutionTimeline
    current_event_index: int = 0
    speed: float = 1.0
    is_playing: bool = False
    is_paused: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "execution_id": self.execution_id,
            "current_event_index": self.current_event_index,
            "speed": self.speed,
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "total_events": len(self.timeline.events),
            "created_at": self.created_at.isoformat(),
        }
