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
import asyncio
import traceback
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.database import async_get_db, get_db_context
from app.schemas.common import ApiResponse
from app.schemas.ui_prototype import (
    UIScreenParseRequest,
    UIFlowGenerateRequest,
)
from app.models.user import User
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen
from app.api.v1.endpoints.auth import get_current_user
from app.crud import ui_prototype as ui_prototype_crud
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.api.v1.endpoints.ui_prototype.helpers import UPLOAD_DIR
from app.core.exception import create_response

router = APIRouter(tags=["UI原型管理"])


@router.post("/parse", response_model=ApiResponse)
async def parse_ui_screens(
    parse_request: UIScreenParseRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"[parse_ui_screens] user_id={current_user.id} screen_ids={parse_request.screen_ids}"
    )
    try:
        if not parse_request.screen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要解析的屏幕",
            )

        def _validate(sync_db: Session):
            # 一次性批量查询所有屏幕，防止N+1及越权风险
            screens = (
                sync_db.query(UIPrototypeScreen)
                .filter(UIPrototypeScreen.id.in_(parse_request.screen_ids))
                .all()
            )
            # 校验所有 screen_id 均存在
            found_ids = {s.id for s in screens}
            missing_ids = set(parse_request.screen_ids) - found_ids
            if missing_ids:
                logger.warning(f"屏幕不存在: {missing_ids}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"屏幕不存在: {missing_ids}",
                )
            # 强约束：所有 screen 必须属于同一项目，避免跨项目调用导致 pipeline 上下文混乱
            screen_project_ids = {s.project_id for s in screens}
            if len(screen_project_ids) > 1:
                logger.warning(
                    f"screen_ids 跨多个项目: project_ids={screen_project_ids}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="screen_ids 必须属于同一项目",
                )
            # 一次性校验所有屏幕均属于当前用户拥有的项目
            authorized_project_ids = {
                pid for (pid,) in sync_db.query(Project.id)
                .filter(Project.id.in_(screen_project_ids), Project.user_id == current_user.id)
                .all()
            }
            unauthorized_project_ids = screen_project_ids - authorized_project_ids
            if unauthorized_project_ids:
                logger.warning(
                    f"用户 user_id={current_user.id} 无权限操作项目 project_ids={unauthorized_project_ids}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限操作此项目",
                )

            return next(iter(screen_project_ids))

        target_project_id = await db.run_sync(_validate)

        # 后台执行解析，使用独立数据库会话，避免请求会话被关闭
        # 不在此处预设 running 状态，由 pipeline.parse_screen() 逐屏设置，保证进度条渐进推进
        async def _run_parse_background():
            try:
                with get_db_context() as bg_db:
                    pipeline = UISpecParsePipeline(
                        bg_db, target_project_id, current_user.id, UPLOAD_DIR,
                        parse_mode=parse_request.parse_mode
                    )
                    result = await pipeline.batch_parse_screens(parse_request.screen_ids)

                    if parse_request.prototype_project_id:
                        ui_prototype_crud.update_prototype_project_stats(
                            bg_db, parse_request.prototype_project_id
                        )

                logger.info(
                    f"[后台解析完成] project_id={target_project_id} "
                    f"success={result.get('success', 0)} failed={result.get('failed', 0)}"
                )
            except Exception as e:
                logger.error(f"[后台解析异常] {e}\n{traceback.format_exc()}")
                # 将仍在 running 或 pending 状态的屏幕标记为 failed
                try:
                    with get_db_context() as bg_db:
                        for screen_id in parse_request.screen_ids:
                            screen = ui_prototype_crud.get_ui_screen_by_id(
                                bg_db, screen_id, target_project_id
                            )
                            if screen and screen.parse_status in ("running", "pending"):
                                ui_prototype_crud.update_ui_screen_parse_status(
                                    bg_db, screen_id, "failed", str(e)
                                )
                except Exception as mark_err:
                    logger.error(f"[后台解析] 标记失败状态异常: {mark_err}")

        task = asyncio.create_task(_run_parse_background())
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)

        return create_response(
            data={
                "task_id": f"parse_{target_project_id}",
                "screen_ids": parse_request.screen_ids,
                "parse_mode": parse_request.parse_mode,
            },
            msg=f"解析任务已启动，共{len(parse_request.screen_ids)}个屏幕"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解析UI屏幕失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解析UI屏幕失败，请稍后重试"
        )


@router.post("/parse/project/{prototype_project_id}", response_model=ApiResponse)
async def parse_prototype_project(
    prototype_project_id: int,
    parse_mode: Optional[str] = Query("text"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _validate(sync_db: Session):
            prototype_project = (
                sync_db.query(UIPrototypeProject)
                .filter(UIPrototypeProject.id == prototype_project_id)
                .first()
            )

            if not prototype_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
                )

            db_project = (
                sync_db.query(Project)
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

            return db_project.id

        project_id = await db.run_sync(_validate)

        # 后台执行解析，使用独立数据库会话
        # 不在此处预设 running 状态，由 pipeline 逐屏设置，保证进度条渐进推进
        async def _run_project_parse_background():
            try:
                with get_db_context() as bg_db:
                    pipeline = UISpecParsePipeline(
                        bg_db, project_id, current_user.id, UPLOAD_DIR,
                        parse_mode=parse_mode
                    )
                    result = await pipeline.parse_prototype_project(prototype_project_id)

                logger.info(
                    f"[后台项目解析完成] prototype_project_id={prototype_project_id} "
                    f"success={result.get('success', 0)} failed={result.get('failed', 0)}"
                )
            except Exception as e:
                logger.error(f"[后台项目解析异常] {e}\n{traceback.format_exc()}")
                # 将仍在 running 或 pending 状态的屏幕标记为 failed
                try:
                    with get_db_context() as bg_db:
                        for status_to_mark in ("running", "pending"):
                            stuck_screens = ui_prototype_crud.get_ui_screens_by_project(
                                db=bg_db,
                                project_id=project_id,
                                user_id=current_user.id,
                                prototype_project_id=prototype_project_id,
                                parse_status=status_to_mark
                            )
                            for s in stuck_screens:
                                ui_prototype_crud.update_ui_screen_parse_status(
                                    bg_db, s.id, "failed", str(e)
                                )
                except Exception as mark_err:
                    logger.error(f"[后台项目解析] 标记失败状态异常: {mark_err}")

        task = asyncio.create_task(_run_project_parse_background())
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)

        return create_response(
            data={
                "task_id": f"parse_project_{prototype_project_id}",
                "prototype_project_id": prototype_project_id,
                "parse_mode": parse_mode,
            },
            msg="解析任务已启动"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"解析原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解析原型项目失败，请稍后重试"
        )


@router.post("/flow/generate", response_model=ApiResponse)
async def generate_page_flow(
    flow_request: UIFlowGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prototype_project_id = flow_request.prototype_project_id or flow_request.project_id
        if not prototype_project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="缺少原型项目ID",
            )

        def _validate_and_create(sync_db: Session):
            prototype_project = (
                sync_db.query(UIPrototypeProject)
                .filter(UIPrototypeProject.id == prototype_project_id)
                .first()
            )

            if not prototype_project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
                )

            db_project = (
                sync_db.query(Project)
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

            return UISpecParsePipeline(
                sync_db, db_project.id, current_user.id, UPLOAD_DIR
            )

        pipeline = await db.run_sync(_validate_and_create)
        success, message = await pipeline.generate_flow(
            prototype_project_id
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


@router.get("/specs/{project_id}", response_model=ApiResponse)
async def get_ui_specs_for_case_generation(
    project_id: int,
    prototype_project_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _get_specs(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(Project.id == project_id, Project.user_id == current_user.id)
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            pipeline = UISpecParsePipeline(sync_db, project_id, current_user.id, UPLOAD_DIR)
            return pipeline.get_parsed_ui_spec_for_case_generation(
                prototype_project_id
            )

        specs = await db.run_sync(_get_specs)
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
