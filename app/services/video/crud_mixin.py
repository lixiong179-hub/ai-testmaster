"""CRUD Mixin - 视频记录的数据库增删改查操作。
"""
from pathlib import Path
from typing import Optional, List
from loguru import logger

from app.models.video_record import VideoRecord
from app.services.video.models import VideoInfo, VideoStatus


class CRUDMixin:
    """视频元信息CRUD操作，封装VideoRecord与VideoInfo之间的转换。"""

    async def save_video_info(
        self,
        task_id: Optional[int],
        test_case_id: Optional[int],
        file_path: str,
        file_name: str,
        file_size: int,
        duration: float = 0.0
    ) -> VideoInfo:
        """保存视频元信息到数据库，返回VideoInfo结构。

        Args:
            task_id: 关联的任务ID，可为None。
            test_case_id: 关联的用例ID，可为None。
            file_path: 视频文件的绝对路径。
            file_name: 视频文件名。
            file_size: 文件大小（字节）。
            duration: 视频时长（秒），默认0.0。

        Returns:
            VideoInfo数据类，包含完整视频元信息。
        """
        video_record = VideoRecord(
            task_id=task_id,
            case_id=test_case_id or 0,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            duration=duration,
            status="completed",
        )
        self.db.add(video_record)
        self.db.commit()
        self.db.refresh(video_record)

        logger.info(f"视频信息已保存: ID={video_record.id}, 文件={file_name}")
        return VideoInfo(
            id=video_record.id,
            task_id=task_id,
            test_case_id=test_case_id,
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            duration=duration,
            status=VideoStatus.READY,
            created_at=video_record.created_at,
        )

    async def get_video_info(self, video_id: int) -> Optional[VideoInfo]:
        """根据ID查询视频元信息，不存在时返回None。

        Args:
            video_id: 视频记录ID。

        Returns:
            VideoInfo或None。
        """
        video = self.db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        if not video:
            return None
        status = VideoStatus.READY
        if video.status == "recording":
            status = VideoStatus.PROCESSING
        elif video.status == "failed":
            status = VideoStatus.FAILED
        return VideoInfo(
            id=video.id,
            task_id=video.task_id,
            test_case_id=video.case_id or None,
            file_path=video.file_path,
            file_name=video.file_name,
            file_size=video.file_size,
            duration=video.duration or 0.0,
            status=status,
            thumbnail_path=video.thumbnail_path,
            created_at=video.created_at,
        )

    async def get_videos_by_task(self, task_id: int) -> List[VideoInfo]:
        """查询指定任务关联的所有视频。

        Args:
            task_id: 任务ID。

        Returns:
            VideoInfo列表。
        """
        videos = self.db.query(VideoRecord).filter(VideoRecord.task_id == task_id).all()
        return [self._to_video_info(v) for v in videos]

    async def get_videos_by_case(self, test_case_id: int) -> List[VideoInfo]:
        """查询指定用例关联的所有视频。

        Args:
            test_case_id: 用例ID。

        Returns:
            VideoInfo列表。
        """
        videos = self.db.query(VideoRecord).filter(VideoRecord.case_id == test_case_id).all()
        return [self._to_video_info(v) for v in videos]

    async def delete_video(self, video_id: int) -> bool:
        """删除视频记录及关联的物理文件（视频和缩略图），不存在时返回False。

        Args:
            video_id: 视频记录ID。

        Returns:
            删除成功返回True，记录不存在返回False。
        """
        video = self.db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        if not video:
            return False

        for path_field in ("file_path", "thumbnail_path"):
            file_path_str = getattr(video, path_field, None)
            if file_path_str:
                file_path = Path(file_path_str)
                try:
                    if file_path.exists():
                        file_path.unlink()
                except OSError as e:
                    logger.warning(f"删除文件失败: {file_path_str}, 错误: {e}")

        self.db.delete(video)
        self.db.commit()
        logger.info(f"视频已删除: ID={video_id}")
        return True

    def _to_video_info(self, video: VideoRecord) -> VideoInfo:
        """将VideoRecord ORM模型转换为VideoInfo数据类。

        Args:
            video: VideoRecord ORM实例。

        Returns:
            VideoInfo数据类。
        """
        status = VideoStatus.READY
        if video.status == "recording":
            status = VideoStatus.PROCESSING
        elif video.status == "failed":
            status = VideoStatus.FAILED
        return VideoInfo(
            id=video.id,
            task_id=video.task_id,
            test_case_id=video.case_id,
            file_path=video.file_path,
            file_name=video.file_name,
            file_size=video.file_size,
            duration=video.duration or 0.0,
            status=status,
            thumbnail_path=video.thumbnail_path,
            created_at=video.created_at,
        )
