"""
执行可视化回放端点模块

本模块定义执行可视化的回放API端点，支持执行过程的回放控制。

路由前缀: /execution（由父模块注册）
标签: 测试执行

端点概览:
    - POST /replay/session              - 创建回放会话
    - POST /replay/{execution_id}/start - 开始回放
    - POST /replay/{execution_id}/pause - 暂停回放
    - POST /replay/{execution_id}/resume - 恢复回放
    - POST /replay/{execution_id}/stop  - 停止回放
    - POST /replay/{execution_id}/seek  - 跳转到指定时间点
    - GET  /replay/{execution_id}/status - 获取回放状态
    - DELETE /replay/{execution_id}     - 关闭回放会话

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.execution_replay_service import (
    ExecutionReplayService,
    get_execution_replay_service
)
from app.api.v1.endpoints.execution_vis_schemas import (
    ReplaySessionRequest,
    ReplaySessionResponse,
    ReplayControlRequest,
    ReplayStatusResponse
)
from loguru import logger

router = APIRouter()


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
        logger.error(f"创建回放会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建回放会话失败"
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
