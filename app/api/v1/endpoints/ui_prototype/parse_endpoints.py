"""
UI原型解析端点模块

本模块定义UI原型解析的API端点，支持AI解析页面结构和生成测试流程。

路由前缀: /ui-prototype（由父模块ui_prototype注册）
标签: UI原型管理

端点概览:
    - POST /screens/{screen_id}/parse    - 解析单个页面
    - POST /projects/{project_id}/parse-all - 批量解析项目所有页面
    - POST /projects/{project_id}/generate-flow - AI生成测试流程

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 解析使用AI模型识别页面元素和交互逻辑
    - 批量解析按页面顺序依次处理
    - 测试流程基于页面间跳转关系自动生成
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.db.database import get_db
from app.schemas.ui_prototype import (
    UIScreenParseRequest,
    UIFlowGenerateRequest,
)
from app.models.user import User
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject
from app.api.v1.endpoints.auth import get_current_user
from app.crud import ui_prototype as ui_prototype_crud
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.api.v1.endpoints.ui_prototype.helpers import UPLOAD_DIR
from app.core.exception import create_response

router = APIRouter(tags=["UI原型管理"])


@router.post("/parse", response_model=dict)
async def parse_ui_screens(
    parse_request: UIScreenParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if not parse_request.screen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要解析的屏幕",
            )

        screen = None
        if parse_request.screen_ids:
            screen = ui_prototype_crud.get_ui_screen_by_id(
                db, parse_request.screen_ids[0]
            )
            if not screen:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"屏幕 {parse_request.screen_ids[0]} 不存在",
                )
            project = (
                db.query(Project)
                .filter(
                    Project.id == screen.project_id,
                    Project.user_id == current_user.id,
                )
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限操作此项目",
                )

        if not screen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供有效的屏幕ID",
            )

        pipeline = UISpecParsePipeline(
            db, screen.project_id, current_user.id, UPLOAD_DIR, parse_mode=parse_request.parse_mode
        )
        result = await pipeline.batch_parse_screens(parse_request.screen_ids)

        if parse_request.prototype_project_id:
            ui_prototype_crud.update_prototype_project_stats(
                db, parse_request.prototype_project_id
            )

        return create_response(
            data=result,
            msg=f"解析完成，成功{result['success']}个，失败{result['failed']}个"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解析UI屏幕失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解析UI屏幕失败，请稍后重试"
        )


@router.post("/parse/project/{prototype_project_id}", response_model=dict)
async def parse_prototype_project(
    prototype_project_id: int,
    parse_mode: Optional[str] = Query("text"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prototype_project = (
            db.query(UIPrototypeProject)
            .filter(UIPrototypeProject.id == prototype_project_id)
            .first()
        )

        if not prototype_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
            )

        db_project = (
            db.query(Project)
            .filter(
                Project.id == prototype_project.project_id,
                Project.user_id == current_user.id,
            )
            .first()
        )

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目或项目不存在",
            )

        pipeline = UISpecParsePipeline(
            db, db_project.id, current_user.id, UPLOAD_DIR, parse_mode=parse_mode
        )
        result = await pipeline.parse_prototype_project(prototype_project_id)

        return create_response(data=result, msg="解析完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解析原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解析原型项目失败，请稍后重试"
        )


@router.post("/flow/generate", response_model=dict)
async def generate_page_flow(
    flow_request: UIFlowGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prototype_project = (
            db.query(UIPrototypeProject)
            .filter(UIPrototypeProject.id == flow_request.prototype_project_id)
            .first()
        )

        if not prototype_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
            )

        db_project = (
            db.query(Project)
            .filter(
                Project.id == prototype_project.project_id,
                Project.user_id == current_user.id,
            )
            .first()
        )

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目或项目不存在",
            )

        pipeline = UISpecParsePipeline(
            db, db_project.id, current_user.id, UPLOAD_DIR
        )
        success, message = await pipeline.generate_flow(
            flow_request.prototype_project_id
        )

        return create_response(
            data={"success": success},
            msg=message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成页面流程失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成页面流程失败，请稍后重试"
        )


@router.get("/specs/{project_id}", response_model=dict)
async def get_ui_specs_for_case_generation(
    project_id: int,
    prototype_project_id: Optional[int] = Query(None),
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

        pipeline = UISpecParsePipeline(db, project_id, current_user.id, UPLOAD_DIR)
        specs = pipeline.get_parsed_ui_spec_for_case_generation(
            prototype_project_id
        )

        return create_response(
            data={"items": specs, "total": len(specs)},
            msg=f"获取成功，共{len(specs)}个屏幕"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取UI规格失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取UI规格失败，请稍后重试"
        )
