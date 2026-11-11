"""UI原型项目端点模块。

本模块定义 UI 原型项目级管理的 API 端点，包括项目 CRUD 与流程数据读写。
路由处理函数已内联（原 `_project_endpoints_routes.py` / `_project_endpoints_flow.py`
已合并），纯辅助函数位于 `app/services/ui_prototype_flow.py`。

路由前缀: /ui-prototype（由父模块 ui_prototype 注册）
标签: UI原型管理

端点概览:
    - POST   /project                                  - 创建原型项目
    - GET    /project/list/{project_id}                - 获取项目原型列表
    - DELETE /project/{prototype_project_id}           - 删除原型项目
    - PUT    /flow/{project_id}                        - 保存流程数据
    - GET    /flow/{project_id}                        - 获取流程数据

公开符号通过本文件 re-export，保持 import 路径不变。
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.project import Project
from app.models.project_flow_data import ProjectFlowData
from app.models.ui_prototype import (
    UIScreenTestCaseLink,
    UIPrototypeProject,
    UIPrototypeScreen,
)
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.ui_prototype import FlowDataSaveRequest, UIPrototypeProjectCreate
from app.services.ui_prototype_flow import (
    _build_flow_summary,
    _count_navigation_edges,
    _serialize_project_flow_data,
)
from app.utils.db_time import utcnow

router = APIRouter(tags=["UI原型管理"])


async def create_prototype_project(
    project_data: UIPrototypeProjectCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 内联 async 实现, 替代 db.run_sync(_create) + sync crud
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_data.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        record = UIPrototypeProject(
            project_id=project_data.project_id,
            name=project_data.name,
            description=project_data.description,
            source=project_data.source,
            created_by=current_user.id,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        data = record
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
        # 内联 async 实现, 替代 db.run_sync(_list) + sync crud
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        skip = (page - 1) * page_size
        # 内联 async 查询替代 get_ui_prototype_projects_by_project
        list_stmt = (
            select(UIPrototypeProject)
            .join(Project)
            .where(
                UIPrototypeProject.project_id == project_id,
                Project.user_id == current_user.id,
            )
        )
        if iteration_id is not None:
            if iteration_id <= 0:
                list_stmt = list_stmt.where(UIPrototypeProject.iteration_id.is_(None))
            else:
                list_stmt = list_stmt.where(
                    UIPrototypeProject.iteration_id == iteration_id
                )
        list_stmt = list_stmt.offset(skip).limit(page_size)
        db_projects_result = await db.execute(list_stmt)
        db_projects = db_projects_result.scalars().all()

        # 内联 async 聚合查询替代 get_ui_prototype_projects_count
        from sqlalchemy import func as sa_func
        count_stmt = (
            select(sa_func.count())
            .select_from(UIPrototypeProject)
            .join(Project)
            .where(
                UIPrototypeProject.project_id == project_id,
                Project.user_id == current_user.id,
            )
        )
        if iteration_id is not None:
            if iteration_id <= 0:
                count_stmt = count_stmt.where(UIPrototypeProject.iteration_id.is_(None))
            else:
                count_stmt = count_stmt.where(
                    UIPrototypeProject.iteration_id == iteration_id
                )
        total = (await db.execute(count_stmt)).scalar() or 0

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

        data = {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
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


async def save_flow_data(
    project_id: int,
    flow_request: FlowDataSaveRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """
    保存项目流程数据（upsert）

    根据project_id保存或更新项目的流程编辑数据（nodes/edges/module_info），
    每个项目仅保留一条记录。存在则更新，不存在则新增。
    """
    try:
        if (
            flow_request.project_id is not None
            and flow_request.project_id != project_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请求体项目ID与路径项目ID不一致",
            )

        # 内联 async 实现, 替代 db.run_sync(_save) + sync crud
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        existing_result = await db.execute(
            select(ProjectFlowData).where(
                ProjectFlowData.project_id == project_id
            )
        )
        existing = existing_result.scalars().first()
        if existing:
            existing.flow_data = flow_request.flow_data
            existing.update_time = utcnow()
            await db.commit()
            await db.refresh(existing)
            result = existing
        else:
            record = ProjectFlowData(
                project_id=project_id,
                flow_data=flow_request.flow_data,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            result = record

        data = _serialize_project_flow_data(result)
        return create_response(data=data, msg="保存成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存项目流程数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存项目流程数据失败，请稍后重试"
        )


async def get_flow_data(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取项目流程数据

    根据project_id查询项目的流程编辑数据。
    若存在已保存数据则返回完整数据，否则返回data=None及提示信息。
    """
    try:
        # 内联 async 实现, 替代 db.run_sync(_get) + sync crud
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )

        flow_result = await db.execute(
            select(ProjectFlowData).where(
                ProjectFlowData.project_id == project_id
            )
        )
        result: Optional[ProjectFlowData] = flow_result.scalars().first()

        if result:
            data = _serialize_project_flow_data(result)
            return create_response(data=data)
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


router.add_api_route(
    "/project",
    create_prototype_project,
    methods=["POST"],
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/project/list/{project_id}",
    get_prototype_projects,
    methods=["GET"],
    response_model=ApiResponse,
)
router.add_api_route(
    "/project/{prototype_project_id}",
    delete_prototype_project,
    methods=["DELETE"],
    response_model=ApiResponse,
)
router.add_api_route(
    "/flow/{project_id}",
    save_flow_data,
    methods=["PUT"],
    response_model=ApiResponse,
)
router.add_api_route(
    "/flow/{project_id}",
    get_flow_data,
    methods=["GET"],
    response_model=ApiResponse,
)

__all__ = [
    "router",
    "_count_navigation_edges",
    "_build_flow_summary",
    "_serialize_project_flow_data",
    "create_prototype_project",
    "get_prototype_projects",
    "delete_prototype_project",
    "save_flow_data",
    "get_flow_data",
]
