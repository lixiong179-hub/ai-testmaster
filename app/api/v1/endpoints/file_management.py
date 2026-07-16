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
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.models.project import Project, ProjectFile
from app.models.iteration import Iteration
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.file import FileUpdateRequest
from app.api.v1.endpoints.file_upload import _file_to_dict
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
        def _query_files(sync_db: Session):
            user_projects = (
                sync_db.query(Project).filter(Project.user_id == current_user.id).all()
            )

            project_ids = [project.id for project in user_projects]

            query = sync_db.query(ProjectFile).filter(
                ProjectFile.project_id.in_(project_ids),
                ProjectFile.is_active.is_(True),
            )

            if resource_type:
                query = query.filter(ProjectFile.resource_type == resource_type)

            if iteration_id is not None:
                if iteration_id <= 0:
                    # <=0 统一视为"未关联迭代"，查询 IS NULL
                    query = query.filter(ProjectFile.iteration_id.is_(None))
                else:
                    query = query.filter(ProjectFile.iteration_id == iteration_id)

            # P1-1: 添加分页支持，避免全量加载
            total = query.count()
            skip = (page - 1) * page_size
            files = query.order_by(
                ProjectFile.resource_type.asc(),
                ProjectFile.sort_order.asc(),
                ProjectFile.upload_time.desc(),
            ).offset(skip).limit(page_size).all()

            return files, total

        files, total = await db.run_sync(_query_files)

        return {
            "code": 200,
            "message": "获取成功",
            "data": {
                "items": [_file_to_dict(f) for f in files],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
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
        def _query_files(sync_db: Session) -> tuple:
            project = (
                sync_db.query(Project)
                .filter(
                    Project.id == project_id, Project.user_id == current_user.id
                )
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限操作此项目",
                )

            query = sync_db.query(ProjectFile).filter(
                ProjectFile.project_id == project_id,
                ProjectFile.is_active.is_(True),
            )

            if resource_type:
                query = query.filter(ProjectFile.resource_type == resource_type)

            if iteration_id is not None:
                if iteration_id <= 0:
                    # <=0 统一视为"未关联迭代"，查询 IS NULL
                    query = query.filter(ProjectFile.iteration_id.is_(None))
                else:
                    query = query.filter(ProjectFile.iteration_id == iteration_id)

            total = query.count()
            skip = (page - 1) * page_size
            files = query.order_by(
                ProjectFile.resource_type.asc(),
                ProjectFile.sort_order.asc(),
                ProjectFile.upload_time.desc(),
            ).offset(skip).limit(page_size).all()

            return files, total

        files, total = await db.run_sync(_query_files)

        return {
            "code": 200,
            "message": "获取成功",
            "data": {
                "items": [_file_to_dict(f) for f in files],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
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
        def _update(sync_db: Session) -> ProjectFile:
            file = sync_db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
            if not file:
                raise HTTPException(status_code=404, detail="文件不存在")

            project = (
                sync_db.query(Project)
                .filter(
                    Project.id == file.project_id,
                    Project.user_id == current_user.id,
                )
                .first()
            )

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
                    iteration = (
                        sync_db.query(Iteration)
                        .filter(
                            Iteration.id == iteration_value,
                            Iteration.project_id == file.project_id,
                        )
                        .first()
                    )
                    if not iteration:
                        raise HTTPException(
                            status_code=400,
                            detail=f"迭代 ID {iteration_value} 不存在或不属于此项目",
                        )

                file.iteration_id = iteration_value

            sync_db.commit()
            sync_db.refresh(file)
            return file

        file = await db.run_sync(_update)

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
        def _delete(sync_db: Session) -> None:
            project = (
                sync_db.query(Project)
                .filter(
                    Project.id == project_id, Project.user_id == current_user.id
                )
                .first()
            )

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限操作此项目",
                )

            file = (
                sync_db.query(ProjectFile)
                .filter(
                    ProjectFile.id == file_id, ProjectFile.project_id == project_id
                )
                .first()
            )

            if not file:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
                )

            file.is_active = False
            sync_db.commit()

        await db.run_sync(_delete)

        return {"code": 200, "message": "删除成功", "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        raise HTTPException(status_code=500, detail="删除文件失败")
