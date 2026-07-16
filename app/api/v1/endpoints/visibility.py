"""
可见模式配置API

与前端testExecution.ts中的visibility API对齐
"""
from typing import Optional
"""
可见性管理端点模块

本模块定义数据可见性控制的API端点，管理项目成员的数据访问权限。

路由前缀: /visibility
标签: 可见性管理

端点概览:
    - GET  /project/{project_id}     - 获取项目可见性设置
    - PUT  /project/{project_id}     - 更新项目可见性设置

权限要求: 所有端点需要Bearer令牌认证，仅项目所有者可操作

业务说明:
    - 可见性控制决定项目数据对其他用户的可见范围
    - 支持公开/私有/团队三种可见性级别
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.visibility_config_service import (
    VisibilityConfig,
    get_visibility_config_service
)

router = APIRouter(prefix="/visibility", tags=["可见模式配置"])


class VisibilityConfigRequest(BaseModel):
    """可见模式配置请求"""
    level: str = Field(..., description="配置级别: global, task, case")
    id: Optional[int] = Field(None, description="任务ID或用例ID")
    headless: bool = Field(True, description="是否无头模式")
    record_video: bool = Field(False, description="是否录制视频")
    video_resolution: list = Field([1280, 720], description="视频分辨率 [宽, 高]")
    video_fps: int = Field(30, ge=15, le=60, description="视频帧率")
    take_screenshot: bool = Field(True, description="是否截图")
    screenshot_on_failure: bool = Field(True, description="失败时截图")
    screenshot_on_success: bool = Field(False, description="成功时截图")
    execution_speed: str = Field("normal", description="执行速度: slow, normal, fast")
    action_delay_ms: int = Field(500, ge=0, le=5000, description="操作延迟毫秒")
    highlight_elements: bool = Field(True, description="高亮元素")
    show_ai_analysis: bool = Field(True, description="显示AI分析")


@router.get("/config")
async def get_visibility_config(
    level: str = Query(..., description="配置级别: global, task, case"),
    id: Optional[int] = Query(None, description="任务ID或用例ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取可见模式配置"""
    service = get_visibility_config_service()

    if level == "global":
        config = service.get_global_config()
    elif level == "task":
        from app.models.test_task import TestTask
        task = None
        if id is not None:
            result = await db.execute(select(TestTask).where(TestTask.id == id))
            task = result.scalar_one_or_none()
        config = service.get_task_config(task) if task else service.get_global_config()
    elif level == "case":
        from app.models.test_case import TestCase
        case = None
        if id is not None:
            result = await db.execute(
                select(TestCase).where(TestCase.id == id, TestCase.is_deleted.is_(False))
            )
            case = result.scalar_one_or_none()
        config = service.get_case_config(case, None) if case else service.get_global_config()
    else:
        config = service.get_global_config()

    return {
        "code": 200,
        "message": "success",
        "data": config.to_dict()
    }


@router.put("/config")
async def update_visibility_config(
    request: VisibilityConfigRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """更新可见模式配置"""
    service = get_visibility_config_service()

    # 构建配置对象
    config_dict = {
        "headless": request.headless,
        "record_video": request.record_video,
        "video_resolution": tuple(request.video_resolution) if isinstance(request.video_resolution, list) else request.video_resolution,
        "video_fps": request.video_fps,
        "take_screenshot": request.take_screenshot,
        "screenshot_on_failure": request.screenshot_on_failure,
        "screenshot_on_success": request.screenshot_on_success,
        "execution_speed": request.execution_speed,
        "action_delay_ms": request.action_delay_ms,
        "highlight_elements": request.highlight_elements,
        "show_ai_analysis": request.show_ai_analysis
    }

    new_config = VisibilityConfig(**config_dict)

    # 验证配置
    is_valid, error_msg = service.validate_config(new_config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # 根据级别更新配置
    if request.level == "global":
        service.set_global_config(new_config)
    elif request.level == "task" and request.id:
        from app.models.test_task import TestTask
        result = await db.execute(select(TestTask).where(TestTask.id == request.id))
        task = result.scalar_one_or_none()
        if task:
            service.update_task_config(task, new_config)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
    elif request.level == "case" and request.id:
        from app.models.test_case import TestCase
        result = await db.execute(
            select(TestCase).where(TestCase.id == request.id, TestCase.is_deleted.is_(False))
        )
        case = result.scalar_one_or_none()
        if case:
            service.update_case_config(case, new_config)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用例不存在"
            )

    return {
        "code": 200,
        "message": "配置已保存",
        "data": new_config.to_dict()
    }
