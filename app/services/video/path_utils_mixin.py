"""路径工具Mixin - 视频文件路径管理工具。
"""
from pathlib import Path
from typing import Optional, Union
from app.models.video_record import VideoRecord


class PathUtilsMixin:
    """视频路径解析工具mixin，提供ID到路径/URL的转换。"""

    def get_video_path(
        self,
        video_id: Optional[int] = None,
        task_id: Optional[int] = None,
        case_id: Optional[int] = None,
    ) -> Optional[Union[str, Path]]:
        """根据视频ID返回存在的物理文件路径。

        Args:
            video_id: 视频记录ID。

        Returns:
            存在的视频文件绝对路径，不存在或记录不存在时返回None。
        """
        if video_id is None and task_id is not None and case_id is not None:
            return self._video_base_dir / f"task_{task_id}_case_{case_id}.webm"

        video = self.db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        if video and video.file_path:
            file_path = Path(video.file_path)
            if file_path.exists():
                return str(file_path)
        return None

    def get_video_url(self, video_id: Union[int, str]) -> Optional[str]:
        """根据视频ID生成流媒体访问URL。

        Args:
            video_id: 视频记录ID。

        Returns:
            相对路径URL格式，如 /api/v1/videos/{id}/stream/{filename}，记录不存在时返回None。
        """
        if isinstance(video_id, str):
            file_path = Path(video_id)
            return f"/videos/{file_path.name}"

        video = self.db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        if video and video.file_path:
            file_name = Path(video.file_path).name
            return f"/api/v1/videos/{video_id}/stream/{file_name}"
        return None

    def _ensure_directory(self, dir_path: str) -> None:
        """确保目录存在，不存在时递归创建。

        Args:
            dir_path: 目录绝对路径。
        """
        Path(dir_path).mkdir(parents=True, exist_ok=True)
