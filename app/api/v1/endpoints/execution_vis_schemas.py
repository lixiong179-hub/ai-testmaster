from typing import Optional, List
"""
执行可视化数据Schema模块

本模块定义执行可视化相关的Pydantic数据模型，用于请求参数校验和响应格式定义。

路由前缀: 无（本模块不定义路由，仅提供Schema定义）

Schema概览:
    - ExecutionVisConfig: 可视化配置模型
    - ExecutionTimelineItem: 时间线条目模型
    - ScreenshotInfo: 截图信息模型
"""
from pydantic import BaseModel, Field, validator


class VideoResolutionSchema(BaseModel):
    width: int = Field(1920, ge=640, le=3840, description="视频宽度")
    height: int = Field(1080, ge=480, le=2160, description="视频高度")


class VisibilityConfigSchema(BaseModel):
    headless: bool = Field(True, description="是否无头模式")
    record_video: bool = Field(False, description="是否录制视频")
    video_resolution: VideoResolutionSchema = Field(default_factory=VideoResolutionSchema, description="视频分辨率")
    video_fps: int = Field(30, ge=15, le=60, description="视频帧率")
    take_screenshot: bool = Field(True, description="是否截图")
    screenshot_on_failure: bool = Field(True, description="失败时截图")
    screenshot_on_success: bool = Field(False, description="成功时截图")
    execution_speed: str = Field("normal", description="执行速度")
    action_delay_ms: int = Field(500, ge=0, le=5000, description="操作延迟毫秒")
    highlight_elements: bool = Field(True, description="高亮元素")
    show_ai_analysis: bool = Field(True, description="显示AI分析")
    hidden_fields: List[str] = Field(default_factory=list, description="API响应中隐藏的字段列表")

    @validator('execution_speed')
    def validate_speed(cls, v: str) -> str:
        if v not in ('slow', 'normal', 'fast'):
            raise ValueError('execution_speed must be slow, normal, or fast')
        return v


class VisibilityConfigResponse(BaseModel):
    config: dict
    level: str
    summary: str


class VideoInfoResponse(BaseModel):
    id: int
    task_id: Optional[int] = None
    test_case_id: Optional[int] = None
    file_path: str = ""
    file_name: str = ""
    file_size: int = 0
    duration: float = 0.0
    status: str = "processing"
    thumbnail_path: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class StorageStatsResponse(BaseModel):
    total_videos: int
    total_size_bytes: int
    total_size_gb: float
    video_directory: str
    retention_days: int
    max_storage_size_gb: int
    storage_usage_percent: float


class ReplaySessionRequest(BaseModel):
    execution_id: str
    video_path: Optional[str] = None
    screenshots: Optional[List[str]] = None


class ReplaySessionResponse(BaseModel):
    execution_id: str
    total_duration: float
    has_video: bool
    screenshot_count: int
    event_count: int


class ReplayControlRequest(BaseModel):
    start_time: float = Field(0.0, description="开始时间（秒）")
    speed: float = Field(1.0, description="回放速度")


class ReplayStatusResponse(BaseModel):
    execution_id: str
    is_playing: bool
    current_time: float
    total_duration: float
    progress_percent: float
    speed: float
    current_event_index: int
    total_events: int
