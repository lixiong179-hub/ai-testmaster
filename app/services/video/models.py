"""数据模型定义 - 定义本子包所需的数据结构、枚举和结果模型。
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VideoStatus(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


class VideoRecordStatus(str, Enum):
    """兼容旧测试导出的录像状态枚举。"""

    PENDING = "pending"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoInfo:
    id: int
    task_id: Optional[int] = None
    test_case_id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    duration: float = 0.0
    status: VideoStatus = VideoStatus.PROCESSING
    thumbnail_path: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "test_case_id": self.test_case_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "duration": self.duration,
            "status": self.status.value,
            "thumbnail_path": self.thumbnail_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
