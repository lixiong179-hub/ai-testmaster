"""
UI原型页面端点模块

本模块定义UI原型页面级管理的API端点，包括页面CRUD和元素标注。

路由前缀: /ui-prototype（由父模块ui_prototype注册）
标签: UI原型管理

端点概览:
    - GET    /screens/{screen_id}          - 获取页面详情
    - PUT    /screens/{screen_id}          - 更新页面信息
    - DELETE /screens/{screen_id}          - 删除页面
    - GET    /screens/{screen_id}/elements - 获取页面元素列表
    - PUT    /screens/{screen_id}/elements - 更新页面元素标注

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 页面元素包括按钮、输入框、链接等可交互组件
    - 元素标注信息用于自动化测试定位
"""
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Body
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.schemas.ui_prototype import UIScreenReviewRequest
from app.models.user import User
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen
from app.api.v1.endpoints.auth import get_current_user
from app.crud import ui_prototype as ui_prototype_crud
from app.api.v1.endpoints.ui_prototype.helpers import _ensure_upload_dir, _build_screen_response, UPLOAD_DIR
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.core.exception import create_response
from loguru import logger

router = APIRouter(tags=["UI原型管理"])


@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_ui_screens(
    project_id: int = Form(...),
    prototype_name: str = Form(...),
    prototype_project_id: Optional[int] = Form(None),
    iteration_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.user_id == current_user.id)
            .first()
        )

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        _ensure_upload_dir()

        saved_files = []
        project_dir = os.path.join(UPLOAD_DIR, str(project_id))
        os.makedirs(project_dir, exist_ok=True)

        for i, file in enumerate(files):
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            ext = (
                os.path.splitext(file.filename)[1] if file.filename else ".png"
            )
            filename = f"{prototype_name}_{timestamp}_{i}{ext}"
            filepath = os.path.join(project_dir, filename)

            try:
                with open(filepath, "wb") as f:
                    shutil.copyfileobj(file.file, f)
            finally:
                if hasattr(file, 'file') and hasattr(file.file, 'close'):
                    file.file.close()

            file_size = os.path.getsize(filepath)

            saved_files.append(
                {
                    "path": filepath,
                    "name": file.filename or filename,
                    "size": file_size,
                }
            )

        if iteration_id is not None and prototype_project_id is None:
            db_iteration_id = None if iteration_id <= 0 else iteration_id
            proto_project = ui_prototype_crud.create_ui_prototype_project(
                db=db,
                project_id=project_id,
                name=prototype_name,
                created_by=current_user.id,
                iteration_id=db_iteration_id,
            )
            prototype_project_id = proto_project.id
        elif iteration_id is not None and prototype_project_id is not None:
            db_iteration_id = None if iteration_id <= 0 else iteration_id
            proto_project = (
                db.query(UIPrototypeProject)
                .filter(UIPrototypeProject.id == prototype_project_id)
                .first()
            )
            if proto_project:
                proto_project.iteration_id = db_iteration_id
                db.commit()

        pipeline = UISpecParsePipeline(
            db, project_id, current_user.id, UPLOAD_DIR
        )
        screen_ids, message = await pipeline.upload_and_create_screens(
            files=saved_files,
            prototype_name=prototype_name,
            prototype_project_id=prototype_project_id,
        )

        return create_response(
            data={"screen_ids": screen_ids, "total": len(screen_ids)},
            msg=message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传UI屏幕失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}",
        )


@router.get("/screens/{project_id}", response_model=dict)
async def get_ui_screens(
    project_id: int,
    prototype_project_id: Optional[int] = Query(None),
    parse_status: Optional[str] = Query(None),
    iteration_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.user_id == current_user.id)
            .first()
        )

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        skip = (page - 1) * page_size
        screens = ui_prototype_crud.get_ui_screens_by_project(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            prototype_project_id=prototype_project_id,
            parse_status=parse_status,
            iteration_id=iteration_id,
            skip=skip,
            limit=page_size,
        )

        total = ui_prototype_crud.get_ui_screens_count(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            prototype_project_id=prototype_project_id,
            parse_status=parse_status,
            iteration_id=iteration_id,
        )

        return create_response(
            data={
                "total": total,
                "items": [_build_screen_response(s) for s in screens],
                "page": page,
                "page_size": page_size,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取UI屏幕列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取UI屏幕列表失败，请稍后重试"
        )


@router.get("/screen/{screen_id}", response_model=dict)
async def get_ui_screen_detail(
    screen_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

        return create_response(
            data={
                "id": screen.id,
                "project_id": screen.project_id,
                "prototype_project_id": screen.prototype_project_id,
                "prototype_name": screen.prototype_name,
                "screen_name": screen.screen_name,
                "screen_order": screen.screen_order,
                "original_file_path": screen.original_file_path,
                "original_file_name": screen.original_file_name,
                "file_type": screen.file_type,
                "file_size": screen.file_size,
                "parse_status": screen.parse_status,
                "parse_status_text": screen.parse_status,
                "parse_model": screen.parse_model,
                "summary": screen.summary,
                "element_count": screen.element_count,
                "button_count": screen.button_count,
                "input_count": screen.input_count,
                "is_entry_point": screen.is_entry_point,
                "is_end_point": screen.is_end_point,
                "review_status": screen.review_status,
                "create_time": screen.create_time,
                "update_time": screen.update_time,
                "ui_spec": screen.ui_spec,
                "layout_checks": screen.layout_checks,
                "navigation_flow": screen.navigation_flow,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取UI屏幕详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取UI屏幕详情失败，请稍后重试"
        )


@router.post("/screen/{screen_id}/review", response_model=dict)
async def review_ui_screen(
    screen_id: int,
    request: UIScreenReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.delete("/screen/{screen_id}", response_model=dict)
async def delete_ui_screen(
    screen_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

        if screen.original_file_path and os.path.exists(screen.original_file_path):
            try:
                os.remove(screen.original_file_path)
            except OSError as e:
                logger.warning(
                    f"删除UI原型文件失败: {screen.original_file_path}, 错误: {e}"
                )

        ui_prototype_crud.delete_ui_screen(db, screen_id)

        return create_response(msg="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除UI屏幕失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除UI屏幕失败，请稍后重试"
        )
