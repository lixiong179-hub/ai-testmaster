"""FFmpeg Mixin - 视频录制、合并、截图和格式转换。
"""
import os
import subprocess
from typing import Optional, Dict, Any
from loguru import logger

from app.services.video.models import VideoInfo


class FFmpegMixin:

    def _check_ffmpeg_available(self) -> bool:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("ffmpeg未安装或不可用")
            return False

    def _check_ffprobe_available(self) -> bool:
        try:
            result = subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("ffprobe未安装或不可用")
            return False

    async def extract_video_thumbnail(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        time_offset: float = 1.0
    ) -> Optional[str]:
        if not self._check_ffmpeg_available():
            logger.warning("ffmpeg不可用，无法提取缩略图")
            return None

        if not self._is_valid_video_path(video_path):
            logger.warning(f"无效的视频路径: {video_path}")
            return None

        if output_path is None:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(
                os.path.dirname(video_path),
                f"{base_name}_thumb.jpg"
            )

        try:
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-ss", str(time_offset),
                "-frames:v", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"视频缩略图提取成功: {output_path}")
                return output_path
            else:
                logger.warning(f"视频缩略图提取失败: {result.stderr[:200]}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg提取缩略图超时")
            return None
        except Exception as e:
            logger.error(f"提取缩略图异常: {e}")
            return None

    async def get_video_duration(self, video_path: str) -> Optional[float]:
        if not self._check_ffprobe_available():
            logger.warning("ffprobe不可用，无法获取视频时长")
            return None

        if not self._is_valid_video_path(video_path):
            return None

        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                logger.debug(f"视频时长: {duration:.2f}秒")
                return duration
            return None

        except (subprocess.TimeoutExpired, ValueError) as e:
            logger.warning(f"获取视频时长失败: {e}")
            return None

    @staticmethod
    def _is_valid_video_path(video_path: str) -> bool:
        if not video_path:
            return False
        if not os.path.exists(video_path):
            return False
        valid_extensions = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv'}
        ext = os.path.splitext(video_path)[1].lower()
        return ext in valid_extensions
