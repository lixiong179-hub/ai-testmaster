"""
UI原型页面管理端点模块

本模块定义UI原型页面的审核和排序管理API端点。

路由前缀: /ui-prototype（由父模块ui_prototype注册）
标签: UI原型管理

端点概览:
    - POST /screen/{screen_id}/review - 审核UI屏幕
    - PUT  /screen/{screen_id}/order  - 更新UI屏幕排序

权限要求: 所有端点需要Bearer令牌认证
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.ui_prototype import UIScreenReviewRequest
from app.models.user import User
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeScreen
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.ui_prototype.helpers import _build_screen_response
from app.core.exception import create_response
from app.utils.db_time import utcnow
from loguru import logger

async def _execute(db: Session, stmt):
    """同步 Session 的查询在线程池执行，避免阻塞事件循环（R2-1）。"""
    return await asyncio.to_thread(db.execute, stmt)


router = APIRouter(tags=["UI原型管理"])


@router.post("/screen/{screen_id}/review", response_model=ApiResponse)
async def review_ui_screen(
    screen_id: int,
    request: UIScreenReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """审核UI屏幕"""
    try:
        screen_result = await _execute(db,
            select(UIPrototypeScreen).where(UIPrototypeScreen.id == screen_id)
        )
        screen = screen_result.scalars().first()
        if not screen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="屏幕不存在"
            )

        project_result = await _execute(db,
            select(Project).where(
                Project.id == screen.project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        # 内联 async 替代 ui_prototype_crud.update_ui_screen_review
        screen.review_status = request.review_status.value
        screen.reviewed_by = current_user.username
        screen.reviewed_at = utcnow()
        screen.review_comment = request.review_comment
        screen.update_time = utcnow()
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, screen)

        return create_response(data=_build_screen_response(screen), msg="审核完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审核UI屏幕失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="审核UI屏幕失败，请稍后重试"
        )


@router.put("/screen/{screen_id}/order", response_model=ApiResponse)
async def update_ui_screen_order(
    screen_id: int,
    screen_order: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新UI屏幕排序"""
    try:
        screen_result = await _execute(db,
            select(UIPrototypeScreen).where(UIPrototypeScreen.id == screen_id)
        )
        screen = screen_result.scalars().first()
        if not screen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="屏幕不存在"
            )

        project_result = await _execute(db,
            select(Project).where(
                Project.id == screen.project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        # 内联 async 替代 ui_prototype_crud.update_ui_screen_order
        screen.screen_order = screen_order
        screen.update_time = utcnow()
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, screen)

        return create_response(data=_build_screen_response(screen), msg="更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新UI屏幕顺序失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新UI屏幕顺序失败，请稍后重试"
        )
