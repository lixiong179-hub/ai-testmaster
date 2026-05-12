"""视频子包 - 通过Mixin组合模式实现测试执行视频的录制与管理。

本子包是视频服务的核心实现，VideoService通过多继承组合各功能Mixin，
实现视频的CRUD操作、FFmpeg处理、路径管理和自动清理。

核心类:
    - VideoService: 视频服务主类（单例模式）

Mixin组合:
    - PathUtilsMixin: 路径工具（目录创建、路径拼接、文件名生成）
    - FFmpegMixin: FFmpeg视频处理（录制、合并、截图、格式转换）
    - CleanupMixin: 自动清理（过期视频删除、磁盘空间管理）
    - CRUDMixin: 数据库CRUD（视频记录创建、查询、更新、删除）

视频生命周期:
    1. 开始录制 -> FFmpegMixin.start_recording
    2. 停止录制 -> FFmpegMixin.stop_recording
    3. 创建记录 -> CRUDMixin.create_video_record
    4. 定期清理 -> CleanupMixin.cleanup_expired_videos
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.services.video.models import VideoInfo, VideoStatus
from app.services.video.crud_mixin import CRUDMixin
from app.services.video.cleanup_mixin import CleanupMixin
from app.services.video.ffmpeg_mixin import FFmpegMixin
from app.services.video.path_utils_mixin import PathUtilsMixin


class VideoService(
    CRUDMixin,
    CleanupMixin,
    FFmpegMixin,
    PathUtilsMixin,
):
    """视频服务 - 组合CRUD/清理/FFmpeg/路径工具四个Mixin。

    采用单例模式，确保全局只有一个视频服务实例。

    使用场景:
        - 测试执行过程视频录制
        - 视频文件管理与查询
        - 过期视频自动清理
    """

    _instance = None

    def __init__(
        self,
        db: Session,
        video_base_dir: str = "/tmp/test_videos",
        retention_days: int = 30
    ):
        """初始化视频服务。

        Args:
            db: 数据库会话。
            video_base_dir: 视频文件存储目录，默认/tmp/test_videos。
            retention_days: 视频保留天数，默认30天。
        """
        self.db = db
        self._video_base_dir = video_base_dir
        self._retention_days = retention_days
        self._ensure_directory(video_base_dir)

    @classmethod
    def get_instance(cls, db: Session, **kwargs) -> 'VideoService':
        """获取单例实例，首次调用时初始化，后续调用更新db。

        Args:
            db: 数据库会话。
            **kwargs: 初始化参数。

        Returns:
            VideoService单例实例。
        """
        if cls._instance is None:
            cls._instance = cls(db, **kwargs)
        else:
            cls._instance.db = db
        return cls._instance


VideoRecordService = VideoService


__all__ = [
    'VideoService',
    'VideoRecordService',
    'VideoInfo',
    'VideoStatus',
    'CRUDMixin',
    'CleanupMixin',
    'FFmpegMixin',
    'PathUtilsMixin',
]


_video_service_instance: Optional[VideoService] = None


def get_video_service(db: Optional[Session] = None) -> VideoService:
    """获取视频服务实例（单例兼容函数）。

    兼容旧版 get_video_service() 无参调用方式。
    若未提供 db，返回已存在的单例实例（可能为None）。

    Args:
        db: 数据库会话，首次初始化时必需。

    Returns:
        VideoService 单例实例。
    """
    global _video_service_instance
    if _video_service_instance is None:
        if db is None:
            raise RuntimeError("首次初始化 VideoService 必须提供 db 参数")
        _video_service_instance = VideoService.get_instance(db)
    elif db is not None:
        _video_service_instance.db = db
    return _video_service_instance
