from typing import Optional
"""
执行可视化配置端点模块

本模块定义执行可视化的配置API端点，管理可视化展示的参数设置。

路由前缀: /execution（由父模块execution.py注册）
标签: 测试执行

端点概览:
    - GET  /vis-config              - 获取可视化配置
    - PUT  /vis-config              - 更新可视化配置

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 配置包括截图质量、视频帧率、展示模式等参数
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.visibility_config_service import (
    VisibilityConfig,
    get_visibility_config_service
)
from app.api.v1.endpoints.execution_vis_schemas import (
    VisibilityConfigSchema,
    VisibilityConfigResponse
)

router = APIRouter()


@router.get("/config/global", response_model=VisibilityConfigResponse)
async def get_global_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    service = get_visibility_config_service()
    config_dict = config.dict()
    if 'video_resolution' in config_dict and isinstance(config_dict['video_resolution'], dict):
        res = config_dict['video_resolution']
        config_dict['video_resolution'] = (res['width'], res['height'])
    new_config = VisibilityConfig(**config_dict)
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
    from app.models.test_task import TestTask
    service = get_visibility_config_service()
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    config_dict = config.dict()
    if 'video_resolution' in config_dict and isinstance(config_dict['video_resolution'], dict):
        res = config_dict['video_resolution']
        config_dict['video_resolution'] = (res['width'], res['height'])
    new_config = VisibilityConfig(**config_dict)
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
