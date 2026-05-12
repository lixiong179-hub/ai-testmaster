"""
UI原型项目端点模块

本模块定义UI原型项目级管理的API端点，包括原型上传、列表查询和删除。

路由前缀: /ui-prototype（由父模块ui_prototype注册）
标签: UI原型管理

端点概览:
    - POST   /projects/{project_id}/upload  - 上传原型文件
    - GET    /projects/{project_id}/list     - 获取项目原型列表
    - DELETE /projects/{project_id}/{prototype_id} - 删除原型

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 支持上传HTML/PDF/图片等原型文件
    - 上传后自动创建页面记录
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.ui_prototype import UIPrototypeProjectCreate, FlowDataSaveRequest
from app.models.user import User
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen, UIScreenTestCaseLink
from app.models.project_flow_data import ProjectFlowData
from app.api.v1.endpoints.auth import get_current_user
from app.crud import ui_prototype as ui_prototype_crud
from app.crud.project_flow_data import save_project_flow_data, get_project_flow_data
from app.core.exception import create_response
from loguru import logger

router = APIRouter(tags=["UI原型管理"])


@router.post(
    "/project",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def create_prototype_project(
    project_data: UIPrototypeProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = (
            db.query(Project)
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

        db_project = ui_prototype_crud.create_ui_prototype_project(
            db=db,
            project_id=project_data.project_id,
            name=project_data.name,
            description=project_data.description,
            source=project_data.source,
            created_by=current_user.id,
        )

        return create_response(
            data=db_project,
            msg="创建成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建UI原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建UI原型项目失败，请稍后重试"
        )


@router.get(
    "/project/list/{project_id}",
    response_model=dict,
)
async def get_prototype_projects(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    iteration_id: Optional[int] = Query(None),
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
        db_projects = ui_prototype_crud.get_ui_prototype_projects_by_project(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            skip=skip,
            limit=page_size,
            iteration_id=iteration_id,
        )

        total = ui_prototype_crud.get_ui_prototype_projects_count(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            iteration_id=iteration_id,
        )

        items = []
        for p in db_projects:
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
                "create_time": p.create_time.isoformat() if p.create_time else None,
                "update_time": p.update_time.isoformat() if p.update_time else None,
            })

        return create_response(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取UI原型项目列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取UI原型项目列表失败，请稍后重试"
        )


@router.delete("/project/{prototype_project_id}", response_model=dict)
async def delete_prototype_project(
    prototype_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        proto_project = (
            db.query(UIPrototypeProject)
            .filter(UIPrototypeProject.id == prototype_project_id)
            .first()
        )

        if not proto_project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
            )

        db_project = (
            db.query(Project)
            .filter(
                Project.id == proto_project.project_id,
                Project.user_id == current_user.id,
            )
            .first()
        )

        if not db_project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        screens = (
            db.query(UIPrototypeScreen)
            .filter(UIPrototypeScreen.prototype_project_id == prototype_project_id)
            .all()
        )

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
            db.query(UIScreenTestCaseLink).filter(
                UIScreenTestCaseLink.screen_id == screen.id
            ).delete()
            db.delete(screen)
            deleted_screens += 1

        db.delete(proto_project)
        db.commit()

        return create_response(
            data={"deleted_screens": deleted_screens},
            msg=f"删除成功，共删除 {deleted_screens} 张图片"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除UI原型项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除UI原型项目失败，请稍后重试"
        )


@router.put("/flow/{project_id}", response_model=dict)
async def save_flow_data(
    project_id: int,
    flow_request: FlowDataSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    保存项目流程数据（upsert）

    根据project_id保存或更新项目的流程编辑数据（nodes/edges/module_info），
    每个项目仅保留一条记录。存在则更新，不存在则新增。
    """
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

        result: ProjectFlowData = save_project_flow_data(
            db=db,
            project_id=project_id,
            flow_data=flow_request.flow_data,
        )

        return create_response(data=_serialize_project_flow_data(result), msg="保存成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存项目流程数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存项目流程数据失败，请稍后重试"
        )


def _serialize_project_flow_data(pfd: ProjectFlowData) -> dict:
    return {
        "id": pfd.id,
        "project_id": pfd.project_id,
        "flow_data": pfd.flow_data,
        "create_time": pfd.create_time.isoformat() if pfd.create_time else None,
        "update_time": pfd.update_time.isoformat() if pfd.update_time else None,
    }


@router.get("/flow/{project_id}", response_model=dict)
async def get_flow_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取项目流程数据

    根据project_id查询项目的流程编辑数据。
    若存在已保存数据则返回完整数据，否则返回data=None及提示信息。
    """
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

        result: Optional[ProjectFlowData] = get_project_flow_data(
            db=db,
            project_id=project_id,
        )

        if result:
            return create_response(data=_serialize_project_flow_data(result))
        else:
            return create_response(data=None, msg="暂无保存数据")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目流程数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目流程数据失败，请稍后重试"
        )
