"""Legacy 视频数据模型 - 兼容原始 video_service.py 的 VideoInfo。"""
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class VideoInfo:
    """视频信息（Legacy兼容版）"""
    id: int
    task_id: int
    case_id: int
    file_path: str
    file_size: int
    duration: Optional[float] = None
    resolution: str = "1920x1080"
    fps: int = 30
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "case_id": self.case_id,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_size_human": self._format_file_size(self.file_size),
            "duration": self.duration,
            "resolution": self.resolution,
            "fps": self.fps,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @staticmethod
    def _format_file_size(size_bytes: float) -> str:
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
