"""
视频记录模型模块

本模块定义了测试执行视频记录（VideoRecord）模型，存储测试执行过程的
视频录制信息，包括文件信息、视频参数和缩略图。

核心类概览：
    - VideoRecord : 视频记录模型

表关系：
    TestTask → VideoRecord（一对多，级联删除）
    TestCase → VideoRecord（一对多，级联删除）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from app.utils.db_time import utcnow

from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class VideoRecord(Base):
    """
    视频记录模型

    存储测试执行视频的相关信息，包括文件路径、视频参数（时长、分辨率、帧率等）
    和缩略图路径。用于测试执行过程的视频回放和问题排查。

    表关系：
        - 多对一 → TestTask（所属任务，级联删除）
        - 多对一 → TestCase（所属用例，级联删除）

    使用场景：
        - 测试执行过程的视频回放
        - 失败用例的视频排查
        - 视频文件管理（大小、格式、时长）
    """
    __tablename__ = "video_records"
    
    id = Column(Integer, primary_key=True, index=True)                                                # 视频记录主键ID
    
    # 关联信息
    task_id = Column(Integer, ForeignKey("test_tasks.id"), nullable=False, index=True)                # 任务ID，级联删除
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True)                # 用例ID，级联删除
    execution_id = Column(String(100), nullable=True, index=True, comment="执行ID")                    # 执行会话ID，关联具体的执行实例
    
    # 文件信息
    file_path = Column(String(500), nullable=False, comment="视频文件路径")                            # 视频文件存储路径
    file_name = Column(String(200), nullable=False, comment="视频文件名")                              # 原始文件名
    file_size = Column(Integer, nullable=False, default=0, comment="文件大小(字节)")                    # 文件大小，单位字节
    file_format = Column(String(20), nullable=False, default="webm", comment="文件格式")                # 视频格式，默认webm
    
    # 视频信息
    duration = Column(Float, nullable=True, comment="视频时长(秒)")                                    # 视频时长，单位秒
    resolution = Column(String(20), nullable=True, default="1920x1080", comment="分辨率")               # 视频分辨率，如1920x1080
    fps = Column(Integer, nullable=True, default=30, comment="帧率")                                  # 视频帧率，默认30fps
    bitrate = Column(Integer, nullable=True, comment="比特率")                                        # 视频比特率，单位bps

    # 缩略图
    thumbnail_path = Column(String(500), nullable=True, comment="缩略图路径")                          # 视频缩略图文件路径

    # 状态
    status = Column(String(20), nullable=False, default="completed", comment="状态: recording/completed/failed")  # recording=录制中，completed=已完成，failed=录制失败
    error_message = Column(Text, nullable=True, comment="错误信息")                                    # 录制失败时的错误信息
    
    # 时间信息
    created_at = Column(DateTime, nullable=False, default=utcnow)                                     # 创建时间，UTC时区
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)                    # 更新时间
    
    # 关联关系
    task = relationship("TestTask", back_populates="video_records")                                   # 所属任务
    case = relationship("TestCase", back_populates="video_records")                                   # 所属用例
    
    def __repr__(self) -> str:
        """返回视频记录的字符串表示，便于调试和日志输出。"""
        return f"<VideoRecord(id={self.id}, task_id={self.task_id}, case_id={self.case_id})>"
    
    def to_dict(self) -> dict:
        """
        将视频记录转换为字典格式。

        Returns:
            dict: 包含所有字段的字典，时间字段转换为ISO格式字符串。
        """
        return {
            "id": self.id,
            "task_id": self.task_id,
            "case_id": self.case_id,
            "execution_id": self.execution_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_format": self.file_format,
            "duration": self.duration,
            "resolution": self.resolution,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "thumbnail_path": self.thumbnail_path,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def file_size_human(self) -> str:
        """
        获取人类可读的文件大小。

        Returns:
            str: 格式化的文件大小字符串，如 "1.50 MB"。
        """
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
