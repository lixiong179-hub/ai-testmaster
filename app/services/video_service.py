"""
视频管理服务

管理测试执行视频的录制、存储、清理和回放
"""
import os
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

from sqlalchemy.orm import Session

from app.models.video_record import VideoRecord


@dataclass
class VideoInfo:
    """视频信息"""
    id: int
    task_id: int
    case_id: int
    file_path: str
    file_size: int
    duration: Optional[float] = None
    resolution: str = "1920x1080"
    fps: int = 30
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "case_id": self.case_id,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_size_human": self._format_file_size(self.file_size),
            "duration": self.duration,
            "resolution": self.resolution,
            "fps": self.fps,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @staticmethod
    def _format_file_size(size_bytes: float) -> str:
        """格式化文件大小"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"


class VideoService:
    """视频管理服务"""
    
    def __init__(self, video_base_dir: str = "./videos"):
        """
        初始化视频服务
        
        Args:
            video_base_dir: 视频基础目录
        """
        self._video_base_dir = Path(video_base_dir)
        self._ensure_directory()
        
        # 默认配置
        self._retention_days = 7  # 默认保留7天
        self._max_storage_size_gb = 10  # 默认最大存储10GB
    
    def _ensure_directory(self):
        """确保视频目录存在"""
        self._video_base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"视频目录: {self._video_base_dir.absolute()}")
    
    def get_video_path(self, task_id: int, case_id: int) -> Path:
        """
        获取视频保存路径
        
        Args:
            task_id: 任务ID
            case_id: 用例ID
            
        Returns:
            视频文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{task_id}_case_{case_id}_{timestamp}.webm"
        return self._video_base_dir / filename
    
    def get_video_url(self, video_path: str) -> str:
        """
        获取视频访问URL
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频URL
        """
        # 相对路径转URL
        relative_path = Path(video_path).relative_to(self._video_base_dir)
        return f"/videos/{relative_path}"
    
    async def save_video_info(self, db: Session, video_info: VideoInfo) -> VideoRecord:
        """
        保存视频信息到数据库
        
        Args:
            db: 数据库会话
            video_info: 视频信息
            
        Returns:
            保存后的视频记录
        """
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
        """
        获取视频信息
        
        Args:
            db: 数据库会话
            video_id: 视频ID
            
        Returns:
            视频信息，如果不存在返回None
        """
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
        """
        获取任务的所有视频
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            
        Returns:
            视频列表
        """
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
        """
        获取用例的所有视频
        
        Args:
            db: 数据库会话
            case_id: 用例ID
            
        Returns:
            视频列表
        """
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
        """
        删除视频
        
        Args:
            db: 数据库会话
            video_id: 视频ID
            
        Returns:
            是否删除成功
        """
        try:
            # 获取视频信息
            video_info = await self.get_video_info(db, video_id)
            if not video_info:
                logger.warning(f"视频不存在: {video_id}")
                return False
            
            # 删除文件
            video_path = Path(video_info.file_path)
            if video_path.exists():
                video_path.unlink()
                logger.info(f"视频文件已删除: {video_path}")
            
            # 删除数据库记录
            db.query(VideoRecord).filter(VideoRecord.id == video_id).delete()
            db.commit()
            
            return True
        except Exception as e:
            logger.error(f"删除视频失败: {e}")
            return False
    
    async def cleanup_expired_videos(self, db: Session, retention_days: Optional[int] = None) -> int:
        """
        清理过期视频
        
        Args:
            db: 数据库会话
            retention_days: 保留天数，默认使用配置值
            
        Returns:
            清理的视频数量
        """
        retention_days = retention_days or self._retention_days
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        deleted_count = 0
        
        try:
            # 查询过期视频
            expired_records = db.query(VideoRecord).filter(
                VideoRecord.created_at < cutoff_date
            ).all()
            
            for record in expired_records:
                if await self.delete_video(db, int(record.id)):
                    deleted_count += 1
            
            # 同时清理没有数据库记录的视频文件
            deleted_count += await self._cleanup_orphaned_videos(cutoff_date)
            
            logger.info(f"已清理 {deleted_count} 个过期视频")
            return deleted_count
        except Exception as e:
            logger.error(f"清理过期视频失败: {e}")
            return deleted_count
    
    async def _cleanup_orphaned_videos(self, cutoff_date: datetime) -> int:
        """
        清理没有数据库记录的孤儿视频文件
        
        Args:
            cutoff_date: 截止日期
            
        Returns:
            清理的文件数量
        """
        deleted_count = 0
        
        try:
            for video_file in self._video_base_dir.glob("*.webm"):
                # 获取文件修改时间
                mtime = datetime.fromtimestamp(video_file.stat().st_mtime)
                if mtime < cutoff_date:
                    video_file.unlink()
                    deleted_count += 1
                    logger.info(f"删除过期视频文件: {video_file}")
        except Exception as e:
            logger.error(f"清理孤儿视频文件失败: {e}")
        
        return deleted_count
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            存储统计
        """
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
                "storage_usage_percent": round((total_size_gb / self._max_storage_size_gb) * 100, 2) if self._max_storage_size_gb > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取存储统计失败: {e}")
            return {
                "total_videos": 0,
                "total_size_bytes": 0,
                "total_size_gb": 0,
                "video_directory": str(self._video_base_dir.absolute()),
                "error": str(e)
            }
    
    def set_retention_policy(self, retention_days: int, max_storage_size_gb: int):
        """
        设置保留策略
        
        Args:
            retention_days: 保留天数
            max_storage_size_gb: 最大存储大小(GB)
        """
        self._retention_days = retention_days
        self._max_storage_size_gb = max_storage_size_gb
        logger.info(f"视频保留策略已更新: 保留{retention_days}天, 最大{max_storage_size_gb}GB")
    
    async def _check_ffmpeg_available(self) -> bool:
        """检查ffmpeg是否可用"""
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
        """
        提取视频缩略图
        
        Args:
            video_path: 视频文件路径
            timestamp: 时间戳（秒）
            
        Returns:
            缩略图字节数据
        """
        # 检查ffmpeg是否可用
        if not await self._check_ffmpeg_available():
            logger.warning("ffmpeg不可用，无法提取缩略图")
            return None
        
        # 验证视频路径
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
                thumbnail_path.unlink()  # 删除临时文件
                return thumbnail_bytes
            else:
                logger.warning(f"提取缩略图失败: {stderr.decode()}")
                return None
        except Exception as e:
            logger.error(f"提取视频缩略图失败: {e}")
            return None
    
    async def _check_ffprobe_available(self) -> bool:
        """检查ffprobe是否可用"""
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
        """
        验证视频路径是否有效（防止目录遍历）
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            是否有效
        """
        try:
            path = Path(video_path).resolve()
            base_path = self._video_base_dir.resolve()
            
            # 检查路径是否在允许的目录内
            return str(path).startswith(str(base_path))
        except Exception:
            return False
    
    async def get_video_duration(self, video_path: str) -> Optional[float]:
        """
        获取视频时长
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频时长（秒）
        """
        # 检查ffprobe是否可用
        if not await self._check_ffprobe_available():
            logger.warning("ffprobe不可用，无法获取视频时长")
            return None
        
        # 验证视频路径
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


# 全局视频服务实例
_video_service: Optional[VideoService] = None


def get_video_service() -> VideoService:
    """获取视频服务实例（单例）"""
    global _video_service
    if _video_service is None:
        _video_service = VideoService()
    return _video_service
