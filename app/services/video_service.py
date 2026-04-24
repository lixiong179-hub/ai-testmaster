"""
视频管理服务 - 兼容代理模块

所有实现已迁移到 video/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.video.legacy_service import VideoService, get_video_service, VideoInfo

__all__ = ["VideoService", "get_video_service", "VideoInfo"]
