from typing import Optional, List
"""
执行视频回放端点模块

本模块定义执行视频回放的API端点，支持测试执行过程的视频录制和回放。

路由前缀: /execution（由父模块execution.py注册）
标签: 测试执行

端点概览:
    - GET  /{execution_id}/video         - 获取执行视频
    - GET  /{execution_id}/video/status  - 获取视频录制状态

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 视频格式为MP4
    - 视频录制在执行过程中自动进行
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.video import get_video_service
from app.services.execution_replay.legacy_service import (
    get_execution_replay_service
)
from app.api.v1.endpoints.execution_vis_schemas import (
    VideoInfoResponse,
    StorageStatsResponse,
    ReplaySessionRequest,
    ReplaySessionResponse,
    ReplayControlRequest,
    ReplayStatusResponse
)
from loguru import logger

router = APIRouter()


@router.get("/videos/stats", response_model=StorageStatsResponse)
async def get_video_storage_stats(
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    # 性能优化：service 内部使用 sync_db.query()，包到独立线程避免阻塞事件循环
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        service = get_video_service(sync_db)
        stats = await run_async_coro_in_thread(service.get_storage_stats())
        total_size_bytes = stats.get("total_size_mb", 0) * 1024 * 1024
        total_size_gb = round(total_size_bytes / (1024 ** 3), 2)
        max_storage_gb = 50
        storage_usage_percent = round((total_size_gb / max_storage_gb) * 100, 1) if max_storage_gb > 0 else 0
        return StorageStatsResponse(
            total_videos=stats.get("total_count", 0),
            total_size_bytes=int(total_size_bytes),
            total_size_gb=total_size_gb,
            video_directory=service._video_base_dir,
            retention_days=service._retention_days,
            max_storage_size_gb=max_storage_gb,
            storage_usage_percent=storage_usage_percent
        )
    finally:
        sync_db.close()


@router.get("/videos/task/{task_id}", response_model=List[VideoInfoResponse])
async def get_task_videos(
    task_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        service = get_video_service(sync_db)
        videos = await run_async_coro_in_thread(service.get_videos_by_task(task_id))
        return [VideoInfoResponse(**v.to_dict()) for v in videos]
    finally:
        sync_db.close()


@router.get("/videos/case/{case_id}", response_model=List[VideoInfoResponse])
async def get_case_videos(
    case_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        service = get_video_service(sync_db)
        videos = await run_async_coro_in_thread(service.get_videos_by_case(case_id))
        return [VideoInfoResponse(**v.to_dict()) for v in videos]
    finally:
        sync_db.close()


@router.delete("/videos/{video_id}")
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        service = get_video_service(sync_db)
        success = await run_async_coro_in_thread(service.delete_video(video_id))
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="视频不存在或删除失败"
            )
        return {"success": True, "message": "视频已删除"}
    finally:
        sync_db.close()


@router.post("/videos/cleanup")
async def cleanup_expired_videos(
    retention_days: Optional[int] = Query(None, description="保留天数"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        service = get_video_service(sync_db)
        result = await run_async_coro_in_thread(service.cleanup_expired_videos(retention_days))
        return {
            "success": True,
            "deleted_count": result.get("deleted_count", 0),
            "failed_count": result.get("failed_count", 0),
            "freed_mb": result.get("freed_mb", 0),
            "retention_days": result.get("retention_days", 0),
            "message": f"已清理 {result.get('deleted_count', 0)} 个过期视频"
        }
    finally:
        sync_db.close()


@router.post("/replay/session", response_model=ReplaySessionResponse)
async def create_replay_session(
    request: ReplaySessionRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    service = get_execution_replay_service()
    sync_db = PrimarySessionLocal()
    try:
        session_info = await run_async_coro_in_thread(
            service.create_replay_session(
                db=sync_db,
                execution_id=request.execution_id,
                video_path=request.video_path,
                screenshots=request.screenshots
            )
        )
        return ReplaySessionResponse(**session_info)
    except Exception as e:
        logger.error(f"创建回放会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建回放会话失败"
        )
    finally:
        sync_db.close()


@router.post("/replay/{execution_id}/start")
async def start_replay(
    execution_id: str,
    request: ReplayControlRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    service = get_execution_replay_service()
    replay_status = await service.get_replay_status(execution_id)
    if not replay_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    return ReplayStatusResponse(**replay_status)


@router.delete("/replay/{execution_id}")
async def close_replay_session(
    execution_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    service = get_execution_replay_service()
    success = await service.close_replay_session(execution_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回放会话不存在"
        )
    return {"success": True, "message": "回放会话已关闭"}
