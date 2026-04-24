"""Legacy FFmpeg Mixin - 兼容原始 video_service.py 的FFmpeg方法。"""
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger


class LegacyFfmpegMixin:
    """Legacy FFmpeg操作，返回bytes的缩略图提取等。"""

    async def _check_ffmpeg_available(self) -> bool:
        try:
            process = await asyncio.create_subprocess_exec(
                'ffmpeg', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(process.communicate(), timeout=5)
            return process.returncode == 0
        except Exception:
            return False

    async def extract_video_thumbnail(self, video_path: str, timestamp: float = 0.0) -> Optional[bytes]:
        if not await self._check_ffmpeg_available():
            logger.warning("ffmpeg不可用，无法提取缩略图")
            return None
        if not self._is_valid_video_path(video_path):
            logger.error(f"无效的视频路径: {video_path}")
            return None
        try:
            thumbnail_path = Path(video_path).with_suffix('.jpg')
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(timestamp),
                '-vframes', '1',
                '-q:v', '2',
                str(thumbnail_path)
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0 and thumbnail_path.exists():
                thumbnail_bytes = thumbnail_path.read_bytes()
                thumbnail_path.unlink()
                return thumbnail_bytes
            else:
                logger.warning(f"提取缩略图失败: {stderr.decode()}")
                return None
        except Exception as e:
            logger.error(f"提取视频缩略图失败: {e}")
            return None

    async def _check_ffprobe_available(self) -> bool:
        try:
            process = await asyncio.create_subprocess_exec(
                'ffprobe', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(process.communicate(), timeout=5)
            return process.returncode == 0
        except Exception:
            return False

    def _is_valid_video_path(self, video_path: str) -> bool:
        try:
            path = Path(video_path).resolve()
            base_path = self._video_base_dir.resolve()
            return str(path).startswith(str(base_path))
        except Exception:
            return False

    async def get_video_duration(self, video_path: str) -> Optional[float]:
        if not await self._check_ffprobe_available():
            logger.warning("ffprobe不可用，无法获取视频时长")
            return None
        if not self._is_valid_video_path(video_path):
            logger.error(f"无效的视频路径: {video_path}")
            return None
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                duration = float(stdout.decode().strip())
                return duration
            else:
                logger.warning(f"获取视频时长失败: {stderr.decode()}")
                return None
        except Exception as e:
            logger.error(f"获取视频时长失败: {e}")
            return None
