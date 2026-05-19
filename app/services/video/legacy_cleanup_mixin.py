"""Legacy 清理Mixin - 兼容原始 video_service.py 的清理逻辑。"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy.orm import Session

from app.models.video_record import VideoRecord
from app.utils.db_time import utcnow


class LegacyCleanupMixin:
    """Legacy 过期视频清理和存储统计。"""

    async def cleanup_expired_videos(
        self, db: Session, retention_days: Optional[int] = None
    ) -> int:
        retention_days = retention_days or self._retention_days
        cutoff_date = utcnow() - timedelta(days=retention_days)
        deleted_count = 0
        try:
            expired_records = db.query(VideoRecord).filter(
                VideoRecord.created_at < cutoff_date
            ).all()
            for record in expired_records:
                if await self.delete_video(db, int(record.id)):
                    deleted_count += 1
            deleted_count += await self._cleanup_orphaned_videos(cutoff_date)
            logger.info(f"已清理 {deleted_count} 个过期视频")
            return deleted_count
        except Exception as e:
            logger.error(f"清理过期视频失败: {e}")
            return deleted_count

    async def _cleanup_orphaned_videos(self, cutoff_date: datetime) -> int:
        deleted_count = 0
        try:
            for video_file in self._video_base_dir.glob("*.webm"):
                mtime = datetime.fromtimestamp(video_file.stat().st_mtime)
                if mtime < cutoff_date:
                    video_file.unlink()
                    deleted_count += 1
                    logger.info(f"删除过期视频文件: {video_file}")
        except Exception as e:
            logger.error(f"清理孤儿视频文件失败: {e}")
        return deleted_count

    async def get_storage_stats(self) -> Dict[str, Any]:
        try:
            total_size = 0
            video_count = 0
            for video_file in self._video_base_dir.glob("*.webm"):
                total_size += video_file.stat().st_size
                video_count += 1
            total_size_gb = total_size / (1024 * 1024 * 1024)
            return {
                "total_videos": video_count,
                "total_size_bytes": total_size,
                "total_size_gb": round(total_size_gb, 2),
                "video_directory": str(self._video_base_dir.absolute()),
                "retention_days": self._retention_days,
                "max_storage_size_gb": self._max_storage_size_gb,
                "storage_usage_percent": round(
                    (total_size_gb / self._max_storage_size_gb) * 100, 2
                ) if self._max_storage_size_gb > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取存储统计失败: {e}")
            return {
                "total_videos": 0,
                "total_size_bytes": 0,
                "total_size_gb": 0,
                "video_directory": str(self._video_base_dir.absolute()),
                "error": "获取存储统计失败"
            }

    def set_retention_policy(self, retention_days: int, max_storage_size_gb: int) -> None:
        self._retention_days = retention_days
        self._max_storage_size_gb = max_storage_size_gb
        logger.info(f"视频保留策略已更新: 保留{retention_days}天, 最大{max_storage_size_gb}GB")
