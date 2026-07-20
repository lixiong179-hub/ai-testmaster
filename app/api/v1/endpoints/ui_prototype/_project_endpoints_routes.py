"""UI原型项目端点 CRUD 路由处理函数。

路由处理函数以普通 async 函数形式定义，由 project_endpoints.py 通过
router.add_api_route 注册，保持 router 定义在原文件中。
"""
import os
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.ui_prototype._project_endpoints_helpers import _build_flow_summary
from app.core.exception import create_response
from app.crud import ui_prototype as ui_prototype_crud
from app.db.database import async_get_db
from app.models.project import Project
from app.models.ui_prototype import (
    UIScreenTestCaseLink,
    UIPrototypeProject,
    UIPrototypeScreen,
)
from app.models.user import User
from app.schemas.ui_prototype import UIPrototypeProjectCreate


async def create_prototype_project(
    project_data: UIPrototypeProjectCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _create(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(
                    Project.id == project_data.project_id,
                    Project.user_id == current_user.id,
                )
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            return ui_prototype_crud.create_ui_prototype_project(
                db=sync_db,
                project_id=project_data.project_id,
                name=project_data.name,
                description=project_data.description,
                source=project_data.source,
                created_by=current_user.id,
            )

        data = await db.run_sync(_create)
        return create_response(data=data, msg="创建成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建UI原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建UI原型项目失败，请稍后重试"
        )


async def get_prototype_projects(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    iteration_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _list(sync_db: Session):
            project = (
                sync_db.query(Project)
                .filter(Project.id == project_id, Project.user_id == current_user.id)
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
                )

            skip = (page - 1) * page_size
            db_projects = ui_prototype_crud.get_ui_prototype_projects_by_project(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                skip=skip,
                limit=page_size,
                iteration_id=iteration_id,
            )

            total = ui_prototype_crud.get_ui_prototype_projects_count(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                iteration_id=iteration_id,
            )

            items = []
            for p in db_projects:
                flow_summary = _build_flow_summary(p.merged_flow)
                items.append({
                    "id": p.id,
                    "project_id": p.project_id,
                    "name": p.name,
                    "description": p.description,
                    "source": p.source,
                    "screen_count": p.screen_count,
                    "parsed_count": p.parsed_count,
                    "parse_status": p.parse_status,
                    "iteration_id": p.iteration_id,
                    "has_flow": flow_summary["has_flow"],
                    "flow_summary": flow_summary,
                    "create_time": p.create_time.isoformat() if p.create_time else None,
                    "update_time": p.update_time.isoformat() if p.update_time else None,
                })

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        data = await db.run_sync(_list)
        return create_response(data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取UI原型项目列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取UI原型项目列表失败，请稍后重试"
        )


async def delete_prototype_project(
    prototype_project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        proto_result = await db.execute(
            select(UIPrototypeProject).where(
                UIPrototypeProject.id == prototype_project_id
            )
        )
        proto_project = proto_result.scalars().first()

        if not proto_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
            )

        db_project_result = await db.execute(
            select(Project).where(
                Project.id == proto_project.project_id,
                Project.user_id == current_user.id,
            )
        )
        db_project = db_project_result.scalars().first()

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        screens_result = await db.execute(
            select(UIPrototypeScreen).where(
                UIPrototypeScreen.prototype_project_id == prototype_project_id
            )
        )
        screens = screens_result.scalars().all()

        deleted_screens = 0
        for screen in screens:
            if screen.original_file_path and os.path.exists(
                screen.original_file_path
            ):
                try:
                    os.remove(screen.original_file_path)
                except OSError as e:
                    logger.warning(
                        f"删除UI原型文件失败: {screen.original_file_path}, 错误: {e}"
                    )
            await db.execute(
                delete(UIScreenTestCaseLink).where(
                    UIScreenTestCaseLink.screen_id == screen.id
                )
            )
            await db.delete(screen)
            deleted_screens += 1

        await db.delete(proto_project)
        await db.commit()

        return create_response(
            data={"deleted_screens": deleted_screens},
            msg=f"删除成功，共删除 {deleted_screens} 张图片"
        )
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除UI原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除UI原型项目失败，请稍后重试"
        )
