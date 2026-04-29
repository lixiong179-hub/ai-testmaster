"""清理Mixin - 自动清理过期视频文件和磁盘空间管理。
"""
from pathlib import Path
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from app.models.video_record import VideoRecord
from app.services.video.models import VideoStatus


class CleanupMixin:
    """过期视频清理和存储统计mixin，基于时间策略删除过期记录和物理文件。"""

    def __init__(self) -> None:
        self._retention_days: int = 30

    async def cleanup_expired_videos(self, days: Optional[int] = None) -> Dict[str, Any]:
        """删除创建时间早于保留期的所有视频记录及物理文件。

        Args:
            days: 保留天数，默认使用实例配置。

        Returns:
            包含deleted_count、failed_count、freed_mb、retention_days的统计字典。
        """
        retention_days = days or self._retention_days
        cutoff = datetime.now() - timedelta(days=retention_days)

        expired_videos = self.db.query(VideoRecord).filter(
            VideoRecord.created_at < cutoff
        ).all()

        deleted_count = 0
        failed_count = 0
        freed_bytes = 0

        for video in expired_videos:
            try:
                file_size = video.file_size or 0
                if video.file_path:
                    file_path = Path(video.file_path)
                    if file_path.exists():
                        file_path.unlink()
                        freed_bytes += file_size

                if video.thumbnail_path:
                    thumb_path = Path(video.thumbnail_path)
                    if thumb_path.exists():
                        thumb_path.unlink()

                self.db.delete(video)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"删除过期视频失败: ID={video.id}, 错误: {e}")
                failed_count += 1

        self.db.commit()

        result = {
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "retention_days": retention_days,
        }

        logger.info(f"过期视频清理完成: 删除{deleted_count}个, 失败{failed_count}个, 释放{result['freed_mb']}MB")
        return result

    async def _cleanup_orphaned_videos(self) -> Dict[str, int]:
        """清理数据库中有记录但物理文件已不存在（孤立）的视频记录。

        Returns:
            包含orphaned_count和cleaned_count的统计字典。
        """
        videos = self.db.query(VideoRecord).all()
        orphaned_count = 0
        cleaned_count = 0

        for video in videos:
            if video.file_path:
                file_path = Path(video.file_path)
                if not file_path.exists():
                    orphaned_count += 1
                    try:
                        self.db.delete(video)
                        cleaned_count += 1
                    except Exception as e:
                        logger.warning(f"清理孤立视频记录失败: ID={video.id}, 错误: {e}")

        self.db.commit()

        logger.info(f"孤立视频清理: 发现{orphaned_count}个, 清理{cleaned_count}个")
        return {"orphaned_count": orphaned_count, "cleaned_count": cleaned_count}

    async def get_storage_stats(self) -> Dict[str, Any]:
        """统计当前所有视频的存储用量，包括记录数和磁盘占用。

        Returns:
            包含total_count、total_size_mb、各状态数量及disk_usage_mb的字典。
        """
        videos = self.db.query(VideoRecord).all()
        total_count = len(videos)
        total_size = sum(v.file_size or 0 for v in videos)
        ready_count = sum(1 for v in videos if v.status == "completed")
        processing_count = sum(1 for v in videos if v.status == "recording")
        failed_count = sum(1 for v in videos if v.status == "failed")

        video_dir = self._video_base_dir
        disk_usage = 0
        if video_dir and Path(video_dir).exists():
            for dirpath, _, filenames in os.walk(video_dir):
                for f in filenames:
                    fp = Path(dirpath) / f
                    try:
                        disk_usage += fp.stat().st_size
                    except OSError:
                        pass

        return {
            "total_count": total_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "ready_count": ready_count,
            "processing_count": processing_count,
            "failed_count": failed_count,
            "disk_usage_mb": round(disk_usage / (1024 * 1024), 2),
        }

    def set_retention_policy(self, days: int) -> None:
        """设置视频保留策略天数。

        Args:
            days: 保留天数，必须大于0。
        """
        if days > 0:
            self._retention_days = days
            logger.info(f"视频保留策略已设置: {days}天")
        else:
            logger.warning(f"无效的保留天数: {days}")
