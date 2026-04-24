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
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.ui_prototype import UIScreenReviewRequest
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.crud import ui_prototype as ui_prototype_crud
from app.api.v1.endpoints.ui_prototype.helpers import _build_screen_response
from app.core.exception import create_response
from loguru import logger

router = APIRouter(tags=["UI原型管理"])


@router.post("/screen/{screen_id}/review", response_model=dict)
async def review_ui_screen(
    screen_id: int,
    request: UIScreenReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """审核UI屏幕"""
    try:
        screen = ui_prototype_crud.get_ui_screen_by_id(db, screen_id)

        if not screen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="屏幕不存在"
            )

        project = (
            db.query(Project)
            .filter(
                Project.id == screen.project_id, Project.user_id == current_user.id
            )
            .first()
        )

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        updated_screen = ui_prototype_crud.update_ui_screen_review(
            db=db,
            screen_id=screen_id,
            review_status=request.review_status.value,
            reviewer=current_user.username,
            review_comment=request.review_comment,
        )

        return create_response(
            data=_build_screen_response(updated_screen),
            msg="审核完成"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"审核UI屏幕失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="审核UI屏幕失败，请稍后重试"
        )


@router.put("/screen/{screen_id}/order", response_model=dict)
async def update_ui_screen_order(
    screen_id: int,
    screen_order: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新UI屏幕排序"""
    try:
        screen = ui_prototype_crud.get_ui_screen_by_id(db, screen_id)

        if not screen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="屏幕不存在"
            )

        project = (
            db.query(Project)
            .filter(
                Project.id == screen.project_id, Project.user_id == current_user.id
            )
            .first()
        )

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        updated_screen = ui_prototype_crud.update_ui_screen_order(
            db, screen_id, screen_order
        )

        return create_response(
            data=_build_screen_response(updated_screen),
            msg="更新成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新UI屏幕顺序失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新UI屏幕顺序失败，请稍后重试"
        )
