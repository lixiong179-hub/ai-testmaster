"""Legacy CRUD Mixin - 兼容原始 video_service.py 的需要db参数的CRUD方法。"""
from pathlib import Path
from typing import Optional, List
from loguru import logger
from sqlalchemy.orm import Session

from app.models.video_record import VideoRecord
from app.services.video.legacy_models import VideoInfo


class LegacyCrudMixin:
    """Legacy CRUD操作，接口与原始video_service.py保持一致。"""

    async def save_video_info(self, db: Session, video_info: VideoInfo) -> VideoRecord:
        try:
            record = VideoRecord(
                task_id=video_info.task_id,
                case_id=video_info.case_id,
                file_path=str(video_info.file_path),
                file_name=Path(video_info.file_path).name,
                file_size=video_info.file_size,
                duration=video_info.duration,
                resolution=video_info.resolution,
                fps=video_info.fps,
                status="completed"
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"视频信息已保存: {video_info.file_path}, ID={record.id}")
            return record
        except Exception as e:
            db.rollback()
            logger.error(f"保存视频信息失败: {e}")
            raise

    async def get_video_info(self, db: Session, video_id: int) -> Optional[VideoInfo]:
        try:
            record = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
            if record:
                return VideoInfo(
                    id=int(record.id),
                    task_id=int(record.task_id),
                    case_id=int(record.case_id),
                    file_path=str(record.file_path),
                    file_size=int(record.file_size),
                    duration=float(record.duration) if record.duration else None,
                    resolution=str(record.resolution) if record.resolution else "",
                    fps=int(record.fps) if record.fps else 30,
                    created_at=record.created_at if record.created_at else None  # type: ignore
                )
            return None
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return None

    async def get_videos_by_task(self, db: Session, task_id: int) -> List[VideoInfo]:
        try:
            records = db.query(VideoRecord).filter(VideoRecord.task_id == task_id).all()
            return [
                VideoInfo(
                    id=int(record.id),
                    task_id=int(record.task_id),
                    case_id=int(record.case_id),
                    file_path=str(record.file_path),
                    file_size=int(record.file_size),
                    duration=float(record.duration) if record.duration else None,
                    resolution=str(record.resolution) if record.resolution else "",
                    fps=int(record.fps) if record.fps else 30,
                    created_at=record.created_at if record.created_at else None  # type: ignore
                )
                for record in records
            ]
        except Exception as e:
            logger.error(f"获取任务视频列表失败: {e}")
            return []

    async def get_videos_by_case(self, db: Session, case_id: int) -> List[VideoInfo]:
        try:
            records = db.query(VideoRecord).filter(VideoRecord.case_id == case_id).all()
            return [
                VideoInfo(
                    id=int(record.id),
                    task_id=int(record.task_id),
                    case_id=int(record.case_id),
                    file_path=str(record.file_path),
                    file_size=int(record.file_size),
                    duration=float(record.duration) if record.duration else None,
                    resolution=str(record.resolution) if record.resolution else "",
                    fps=int(record.fps) if record.fps else 30,
                    created_at=record.created_at if record.created_at else None  # type: ignore
                )
                for record in records
            ]
        except Exception as e:
            logger.error(f"获取用例视频列表失败: {e}")
            return []

    async def delete_video(self, db: Session, video_id: int) -> bool:
        try:
            video_info = await self.get_video_info(db, video_id)
            if not video_info:
                logger.warning(f"视频不存在: {video_id}")
                return False
            video_path = Path(video_info.file_path)
            if video_path.exists():
                video_path.unlink()
                logger.info(f"视频文件已删除: {video_path}")
            db.query(VideoRecord).filter(VideoRecord.id == video_id).delete()
            db.commit()
            return True
        except Exception as e:
            logger.error(f"删除视频失败: {e}")
            return False
