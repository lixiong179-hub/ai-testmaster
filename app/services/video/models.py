"""数据模型定义 - 定义本子包所需的数据结构、枚举和结果模型。
"""
from typing import Optional, Dict, Any
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


class VideoInfo:
    def __init__(
        self,
        id: int,
        task_id: Optional[int] = None,
        test_case_id: Optional[int] = None,
        case_id: Optional[int] = None,
        file_path: str = "",
        file_name: str = "",
        file_size: int = 0,
        duration: float = 0.0,
        resolution: Optional[str] = None,
        fps: Optional[int] = None,
        file_format: str = "webm",
        status: VideoStatus = VideoStatus.PROCESSING,
        thumbnail_path: Optional[str] = None,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ):
        self.id = id
        self.task_id = task_id
        self.test_case_id = test_case_id if test_case_id is not None else case_id
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.duration = duration
        self.resolution = resolution
        self.fps = fps
        self.file_format = file_format
        self.status = status
        self.thumbnail_path = thumbnail_path
        self.created_at = created_at
        self.expires_at = expires_at

    @property
    def case_id(self) -> Optional[int]:
        return self.test_case_id

    @staticmethod
    def _format_file_size(size: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")
        value = float(size or 0)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.2f} {unit}"
            value /= 1024
        return f"{value:.2f} TB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "test_case_id": self.test_case_id,
            "case_id": self.test_case_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_size_human": self._format_file_size(self.file_size),
            "duration": self.duration,
            "resolution": self.resolution,
            "fps": self.fps,
            "file_format": self.file_format,
            "status": self.status.value,
            "thumbnail_path": self.thumbnail_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
