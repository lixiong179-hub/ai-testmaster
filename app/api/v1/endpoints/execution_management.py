"""
执行管理端点模块

本模块定义测试执行的管理API端点，包括截图获取和视频回放。

路由前缀: /execution（由父模块execution.py注册）
标签: 测试执行

端点概览:
    - GET /{task_id}/screenshot/{case_id}/{step_number}/{type} - 获取步骤截图
    - GET /{task_id}/case/{case_id}/video                      - 获取执行视频
    - GET /{task_id}/case/{case_id}/video/info                 - 获取视频信息

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 截图按任务/用例/步骤/类型组织存储
    - 视频通过VideoService管理，支持按任务和用例查询
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.test_task import TestTask
from app.api.v1.endpoints.auth import get_current_user
from app.services.video import get_video_service
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


@router.get("/{task_id}/screenshot/{case_id}/{step_number}/{type}")
async def get_step_screenshot(
    task_id: int,
    case_id: int,
    step_number: int,
    type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取步骤截图"""
    try:
        from fastapi.responses import FileResponse

        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        from app.api.v1.endpoints.execution_core import verify_project_permission
        verify_project_permission(db, task.project_id, current_user.id)

        screenshot_dir = f"./screenshots/{task_id}/{case_id}"
        screenshot_path = f"{screenshot_dir}/{step_number}_{type}.png"

        import os
        if os.path.exists(screenshot_path):
            return FileResponse(screenshot_path)

        return create_response(code=404, message="截图不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取截图失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取截图失败"
        )


@router.get("/{task_id}/case/{case_id}/video")
async def get_execution_video(
    task_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取执行视频"""
    try:
        from fastapi.responses import FileResponse

        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        from app.api.v1.endpoints.execution_core import verify_project_permission
        verify_project_permission(db, task.project_id, current_user.id)

        service = get_video_service(db)
        videos = await service.get_videos_by_task(task_id)

        for video in videos:
            if video.case_id == case_id and video.file_path:
                import os
                if os.path.exists(video.file_path):
                    return FileResponse(
                        video.file_path,
                        media_type="video/mp4",
                        filename=f"task_{task_id}_case_{case_id}.mp4"
                    )

        return create_response(code=404, message="视频不存在或未启用录制")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取视频失败"
        )


@router.get("/{task_id}/case/{case_id}/video/info")
async def get_video_info(
    task_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取视频信息"""
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        from app.api.v1.endpoints.execution_core import verify_project_permission
        verify_project_permission(db, task.project_id, current_user.id)

        service = get_video_service(db)
        videos = await service.get_videos_by_case(case_id)

        if videos:
            video = videos[0]
            return create_response(data=video.to_dict())

        return create_response(code=404, message="视频不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取视频信息失败"
        )
