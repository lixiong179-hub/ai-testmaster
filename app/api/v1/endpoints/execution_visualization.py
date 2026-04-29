"""
执行过程可视化API

提供可见模式配置、视频管理和执行回放的API端点
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.visibility_config_service import (
    VisibilityConfigService,
    VisibilityConfig,
    get_visibility_config_service
)
from app.services.video_service import VideoService, VideoInfo, get_video_service
from app.services.execution_replay_service import (
    ExecutionReplayService,
    get_execution_replay_service
)

from app.api.v1.endpoints.execution_vis_video_replay import router as video_replay_router


router = APIRouter()


# ============================================================================
# Pydantic模型
# ============================================================================

class VideoResolutionSchema(BaseModel):
    """视频分辨率Schema"""
    width: int = Field(1920, ge=640, le=3840, description="视频宽度")
    height: int = Field(1080, ge=480, le=2160, description="视频高度")


class VisibilityConfigSchema(BaseModel):
    """可见模式配置Schema"""
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
    
    @validator('execution_speed')
    def validate_speed(cls, v):
        """验证执行速度"""
        if v not in ('slow', 'normal', 'fast'):
            raise ValueError('execution_speed must be slow, normal, or fast')
        return v


class VisibilityConfigResponse(BaseModel):
    """可见模式配置响应"""
    config: dict
    level: str
    summary: str


class VideoInfoResponse(BaseModel):
    """视频信息响应"""
    id: int
    task_id: int
    case_id: int
    file_path: str
    file_size: int
    file_size_human: str
    duration: Optional[float]
    resolution: str
    fps: int
    created_at: Optional[str]


class StorageStatsResponse(BaseModel):
    """存储统计响应"""
    total_videos: int
    total_size_bytes: int
    total_size_gb: float
    video_directory: str
    retention_days: int
    max_storage_size_gb: int
    storage_usage_percent: float


class ReplaySessionRequest(BaseModel):
    """回放会话请求"""
    execution_id: str
    video_path: Optional[str] = None
    screenshots: Optional[List[str]] = None


class ReplaySessionResponse(BaseModel):
    """回放会话响应"""
    execution_id: str
    total_duration: float
    has_video: bool
    screenshot_count: int
    event_count: int


class ReplayControlRequest(BaseModel):
    """回放控制请求"""
    start_time: float = Field(0.0, description="开始时间（秒）")
    speed: float = Field(1.0, description="回放速度")


class ReplayStatusResponse(BaseModel):
    """回放状态响应"""
    execution_id: str
    is_playing: bool
    current_time: float
    total_duration: float
    progress_percent: float
    speed: float
    current_event_index: int
    total_events: int


# ============================================================================
# 可见模式配置API
# ============================================================================

@router.get("/config/global", response_model=VisibilityConfigResponse)
async def get_global_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取全局可见模式配置"""
    service = get_visibility_config_service()
    config = service.get_global_config()
    
    return VisibilityConfigResponse(
        config=config.to_dict(),
        level="global",
        summary=service.get_config_summary(config)
    )


@router.put("/config/global", response_model=VisibilityConfigResponse)
async def update_global_config(
    config: VisibilityConfigSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新全局可见模式配置"""
    service = get_visibility_config_service()
    
    config_dict = config.dict()
    # 转换video_resolution为tuple
    if 'video_resolution' in config_dict and isinstance(config_dict['video_resolution'], dict):
        res = config_dict['video_resolution']
        config_dict['video_resolution'] = (res['width'], res['height'])
    new_config = VisibilityConfig(**config_dict)
    
    # 验证配置
    is_valid, error_msg = service.validate_config(new_config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    service.set_global_config(new_config)
    
    return VisibilityConfigResponse(
        config=new_config.to_dict(),
        level="global",
        summary=service.get_config_summary(new_config)
    )


@router.get("/config/task/{task_id}", response_model=VisibilityConfigResponse)
async def get_task_config(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务级别的可见模式配置"""
    from app.models.test_task import TestTask
    
    service = get_visibility_config_service()
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    config = service.get_task_config(task)
    
    return VisibilityConfigResponse(
        config=config.to_dict(),
        level="task",
        summary=service.get_config_summary(config)
    )


@router.put("/config/task/{task_id}", response_model=VisibilityConfigResponse)
async def update_task_config(
    task_id: int,
    config: VisibilityConfigSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新任务的可见模式配置"""
    from app.models.test_task import TestTask
    
    service = get_visibility_config_service()
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    config_dict = config.dict()
    # 转换video_resolution为tuple
    if 'video_resolution' in config_dict and isinstance(config_dict['video_resolution'], dict):
        res = config_dict['video_resolution']
        config_dict['video_resolution'] = (res['width'], res['height'])
    new_config = VisibilityConfig(**config_dict)
    
    # 验证配置
    is_valid, error_msg = service.validate_config(new_config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    service.update_task_config(task, new_config)
    db.commit()
    
    return VisibilityConfigResponse(
        config=new_config.to_dict(),
        level="task",
        summary=service.get_config_summary(new_config)
    )


@router.get("/config/case/{case_id}", response_model=VisibilityConfigResponse)
async def get_case_config(
    case_id: int,
    task_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用例级别的可见模式配置"""
    from app.models.test_case import TestCase
    from app.models.test_task import TestTask
    
    service = get_visibility_config_service()
    case = db.query(TestCase).filter(TestCase.id == case_id).first()
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用例不存在"
        )
    
    task = None
    if task_id:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
    
    config = service.get_case_config(case, task)
    
    return VisibilityConfigResponse(
        config=config.to_dict(),
        level="case",
        summary=service.get_config_summary(config)
    )


# ============================================================================
# 视频管理API
# ============================================================================

@router.get("/videos/stats", response_model=StorageStatsResponse)
async def get_video_storage_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取视频存储统计"""
    service = get_video_service()
    stats = await service.get_storage_stats()
    return StorageStatsResponse(**stats)


@router.get("/videos/task/{task_id}", response_model=List[VideoInfoResponse])
async def get_task_videos(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务的所有视频"""
    service = get_video_service()
    videos = await service.get_videos_by_task(db, task_id)
    return [VideoInfoResponse(**v.to_dict()) for v in videos]


@router.get("/videos/case/{case_id}", response_model=List[VideoInfoResponse])
async def get_case_videos(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用例的所有视频"""
    service = get_video_service()
    videos = await service.get_videos_by_case(db, case_id)
    return [VideoInfoResponse(**v.to_dict()) for v in videos]


@router.delete("/videos/{video_id}")
async def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除视频"""
    service = get_video_service()
    success = await service.delete_video(db, video_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="视频不存在或删除失败"
        )
    
    return {"success": True, "message": "视频已删除"}


@router.post("/videos/cleanup")
async def cleanup_expired_videos(
    retention_days: Optional[int] = Query(None, description="保留天数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理过期视频"""
    service = get_video_service()
    deleted_count = await service.cleanup_expired_videos(db, retention_days)
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "message": f"已清理 {deleted_count} 个过期视频"
    }


# ============================================================================
# 执行回放API
# ============================================================================

@router.post("/replay/session", response_model=ReplaySessionResponse)
async def create_replay_session(
    request: ReplaySessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建回放会话"""
    service = get_execution_replay_service()
    
    try:
        session_info = await service.create_replay_session(
            db=db,
            execution_id=request.execution_id,
            video_path=request.video_path,
            screenshots=request.screenshots
        )
        return ReplaySessionResponse(**session_info)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建回放会话失败: {str(e)}"
        )


@router.post("/replay/{execution_id}/start")
async def start_replay(
    execution_id: str,
    request: ReplayControlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """开始回放"""
    service = get_execution_replay_service()
    
    success = await service.start_replay(
        execution_id=execution_id,
        start_time=request.start_time,
        speed=request.speed
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法开始回放，会话可能不存在或已在播放"
        )
    
    return {"success": True, "message": "回放已开始"}


@router.post("/replay/{execution_id}/pause")
async def pause_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """暂停回放"""
    service = get_execution_replay_service()
    
    success = await service.pause_replay(execution_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    
    return {"success": True, "message": "回放已暂停"}


@router.post("/replay/{execution_id}/resume")
async def resume_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """恢复回放"""
    service = get_execution_replay_service()
    
    success = await service.resume_replay(execution_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    
    return {"success": True, "message": "回放已恢复"}


@router.post("/replay/{execution_id}/stop")
async def stop_replay(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """停止回放"""
    service = get_execution_replay_service()
    
    success = await service.stop_replay(execution_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    
    return {"success": True, "message": "回放已停止"}


@router.post("/replay/{execution_id}/seek")
async def seek_replay(
    execution_id: str,
    timestamp: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """跳转到指定时间点"""
    service = get_execution_replay_service()
    
    success = await service.seek_to(execution_id, timestamp)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    
    return {"success": True, "message": f"已跳转到 {timestamp}s"}


@router.get("/replay/{execution_id}/status", response_model=ReplayStatusResponse)
async def get_replay_status(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取回放状态"""
    service = get_execution_replay_service()
    
    status = await service.get_replay_status(execution_id)
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    
    return ReplayStatusResponse(**status)


@router.delete("/replay/{execution_id}")
async def close_replay_session(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """关闭回放会话"""
    service = get_execution_replay_service()
    
    success = await service.close_replay_session(execution_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    
    return {"success": True, "message": "回放会话已关闭"}
router.include_router(video_replay_router)
