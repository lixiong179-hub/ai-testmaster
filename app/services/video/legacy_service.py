"""Legacy 视频服务 - 兼容原始 video_service.py 的完整实现。"""
from typing import Optional
from pathlib import Path

from app.services.video.legacy_models import VideoInfo
from app.services.video.legacy_crud_mixin import LegacyCrudMixin
from app.services.video.legacy_ffmpeg_mixin import LegacyFfmpegMixin
from app.services.video.legacy_cleanup_mixin import LegacyCleanupMixin
from app.services.video.legacy_utils_mixin import LegacyUtilsMixin


class VideoService(LegacyCrudMixin, LegacyFfmpegMixin, LegacyCleanupMixin, LegacyUtilsMixin):
    """视频管理服务（Legacy兼容版）"""

    def __init__(self, video_base_dir: str = "./videos"):
        self._video_base_dir = Path(video_base_dir)
        self._ensure_directory()
        self._retention_days = 7
        self._max_storage_size_gb = 10

    def _ensure_directory(self):
        self._video_base_dir.mkdir(parents=True, exist_ok=True)


_video_service: Optional[VideoService] = None


def get_video_service() -> VideoService:
    """获取视频服务实例（单例）"""
    global _video_service
    if _video_service is None:
        _video_service = VideoService()
    return _video_service


__all__ = [
    "VideoService",
    "get_video_service",
    "VideoInfo",
]
