"""
视频管理服务 - 兼容代理模块

所有实现已迁移到 video/ 子包，统一从 app.services.video 导入。
本文件保留以兼容现有引用，将在后续版本中移除。
"""
from app.services.video import VideoService, VideoInfo, get_video_service

__all__ = ["VideoService", "VideoInfo", "get_video_service"]
