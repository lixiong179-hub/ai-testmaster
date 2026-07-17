"""
文件管理端点模块

本模块定义文件的管理API端点，包括文件列表查询、详情获取和删除操作。

路由前缀: /file（由父模块file.py注册）
标签: 文件管理

端点概览:
    - GET    /list                - 获取文件列表（分页）
    - GET    /{file_id}           - 获取文件详情
    - DELETE /{file_id}           - 删除文件
    - GET    /project/{project_id} - 获取项目关联文件

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 文件列表支持按项目ID和文件类型筛选
    - 删除为物理删除，同时移除磁盘文件
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
)
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.models.project import Project, ProjectFile
from app.models.iteration import Iteration
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.file import FileUpdateRequest
from app.api.v1.endpoints.file_upload import _file_to_dict
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


@router.get("/list", response_model=ApiResponse)
async def get_all_files(
    resource_type: str = None,
    iteration_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user_projects_result = await db.execute(
            select(Project).where(Project.user_id == current_user.id)
        )
        user_projects = user_projects_result.scalars().all()

        project_ids = [project.id for project in user_projects]

        conditions = [
            ProjectFile.project_id.in_(project_ids),
            ProjectFile.is_active.is_(True),
        ]

        if resource_type:
            conditions.append(ProjectFile.resource_type == resource_type)

        if iteration_id is not None:
            if iteration_id <= 0:
                # <=0 统一视为"未关联迭代"，查询 IS NULL
                conditions.append(ProjectFile.iteration_id.is_(None))
            else:
                conditions.append(ProjectFile.iteration_id == iteration_id)

        # P1-1: 添加分页支持，避免全量加载
        total_result = await db.execute(
            select(func.count()).select_from(ProjectFile).where(*conditions)
        )
        total = total_result.scalar() or 0
        skip = (page - 1) * page_size
        files_result = await db.execute(
            select(ProjectFile)
            .where(*conditions)
            .order_by(
                ProjectFile.resource_type.asc(),
                ProjectFile.sort_order.asc(),
                ProjectFile.upload_time.desc(),
            )
            .offset(skip)
            .limit(page_size)
        )
        files = files_result.scalars().all()

        return create_response(
            data={
                "items": [_file_to_dict(f) for f in files],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            msg="获取成功",
        )
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(
            status_code=500, detail="获取文件列表失败"
        )


@router.get("/list/{project_id}", response_model=ApiResponse)
async def get_file_list(
    project_id: int,
    resource_type: str = None,
    iteration_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目",
            )

        conditions = [
            ProjectFile.project_id == project_id,
            ProjectFile.is_active.is_(True),
        ]

        if resource_type:
            conditions.append(ProjectFile.resource_type == resource_type)

        if iteration_id is not None:
            if iteration_id <= 0:
                # <=0 统一视为"未关联迭代"，查询 IS NULL
                conditions.append(ProjectFile.iteration_id.is_(None))
            else:
                conditions.append(ProjectFile.iteration_id == iteration_id)

        total_result = await db.execute(
            select(func.count()).select_from(ProjectFile).where(*conditions)
        )
        total = total_result.scalar() or 0
        skip = (page - 1) * page_size
        files_result = await db.execute(
            select(ProjectFile)
            .where(*conditions)
            .order_by(
                ProjectFile.resource_type.asc(),
                ProjectFile.sort_order.asc(),
                ProjectFile.upload_time.desc(),
            )
            .offset(skip)
            .limit(page_size)
        )
        files = files_result.scalars().all()

        return create_response(
            data={
                "items": [_file_to_dict(f) for f in files],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            msg="获取成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(
            status_code=500, detail="获取文件列表失败"
        )


@router.put("/{file_id}", response_model=ApiResponse)
async def update_file(
    file_id: int,
    update_data: FileUpdateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        file_result = await db.execute(
            select(ProjectFile).where(ProjectFile.id == file_id)
        )
        file = file_result.scalars().first()
        if not file:
            raise HTTPException(status_code=404, detail="文件不存在")

        project_result = await db.execute(
            select(Project).where(
                Project.id == file.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalars().first()

        if not project:
            raise HTTPException(status_code=403, detail="无权限操作此项目")

        if update_data.resource_type:
            file.resource_type = (
                update_data.resource_type.value
                if hasattr(update_data.resource_type, "value")
                else update_data.resource_type
            )

        if update_data.description is not None:
            file.description = update_data.description

        if update_data.is_active is not None:
            file.is_active = update_data.is_active

        if update_data.iteration_id is not None:
            iteration_value = (
                update_data.iteration_id
                if update_data.iteration_id > 0
                else None
            )

            if iteration_value:
                iteration_result = await db.execute(
                    select(Iteration).where(
                        Iteration.id == iteration_value,
                        Iteration.project_id == file.project_id,
                    )
                )
                iteration = iteration_result.scalars().first()
                if not iteration:
                    raise HTTPException(
                        status_code=400,
                        detail=f"迭代 ID {iteration_value} 不存在或不属于此项目",
                    )

            file.iteration_id = iteration_value

        await db.commit()
        await db.refresh(file)

        return {
            "code": 200,
            "message": "更新成功",
            "data": _file_to_dict(file),
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新文件失败: {e}")
        raise HTTPException(status_code=500, detail="更新文件失败")


@router.delete("/{file_id}", response_model=ApiResponse)
async def delete_file(
    file_id: int,
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project_result = await db.execute(
            select(Project).where(
                Project.id == project_id, Project.user_id == current_user.id
            )
        )
        project = project_result.scalars().first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目",
            )

        file_result = await db.execute(
            select(ProjectFile).where(
                ProjectFile.id == file_id, ProjectFile.project_id == project_id
            )
        )
        file = file_result.scalars().first()

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
            )

        file.is_active = False
        await db.commit()

        return {"code": 200, "message": "删除成功", "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        raise HTTPException(status_code=500, detail="删除文件失败")
