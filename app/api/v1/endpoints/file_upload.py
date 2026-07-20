"""
文件上传端点模块

本模块定义单文件上传的API端点，支持多种文件类型的上传和存储。

路由前缀: /file（由父模块file.py注册）
标签: 文件管理

端点概览:
    - POST /upload - 上传单个文件

权限要求: 需要Bearer令牌认证

业务说明:
    - 支持需求文档、测试数据、附件等多种文件类型
    - 文件存储在uploads目录下
    - 支持按项目ID关联文件
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    Body,
)
from typing import List, Optional
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.project import Project, ProjectFile
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.file import UrlSubmitRequest
from app.crud import file as file_crud
from app.core.config import settings
import uuid
from app.utils.file_utils import (
    validate_file_format,
    get_file_size,
    detect_resource_type,
    validate_file_mime,
)
from loguru import logger
import os

try:
    import magic

    _MAGIC_AVAILABLE = True
except ImportError:
    _MAGIC_AVAILABLE = False

router = APIRouter()


def _file_to_dict(file: ProjectFile) -> dict:
    return {
        "id": file.id,
        "project_id": file.project_id,
        "file_name": file.file_name,
        "file_type": file.file_type,
        "file_url": file.file_url,
        "file_source": file.file_source,
        "size": file.size,
        "upload_time": file.upload_time,
        "resource_type": file.resource_type,
        "content": file.content,
        "extract_status": file.extract_status,
        "extract_error": file.extract_error,
        "extracted_at": file.extracted_at,
        "description": file.description,
        "is_active": file.is_active,
        "sort_order": file.sort_order,
        "linked_case_count": file.linked_case_count,
        "iteration_id": file.iteration_id,
    }


def _auto_detect_resource_type(filename: str, file_ext: str) -> str:
    return detect_resource_type(filename, file_ext)


@router.post("/upload", response_model=ApiResponse)
async def upload_file(
    project_id: int = Form(...),
    file: UploadFile = File(...),
    resource_type: str = Form("other"),
    description: str = Form(""),
    iteration_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    saved_file_path = None
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

        file_ext = validate_file_format(file.filename)
        if not file_ext:
            raise HTTPException(status_code=400, detail="不支持的文件格式")

        allowed_extensions = settings.allowed_extensions_list
        if allowed_extensions and file_ext.lower() not in [
            e.lower().lstrip(".") for e in allowed_extensions
        ]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"不允许的文件类型: .{file_ext}，"
                    f"允许的类型: {', '.join(allowed_extensions)}"
                ),
            )

        contents = await file.read()
        if len(contents) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"文件过大，最大允许 "
                    f"{settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB"
                ),
            )

        if _MAGIC_AVAILABLE:
            try:
                detected_mime = magic.from_buffer(contents, mime=True)
                mime_error = validate_file_mime(file_ext, detected_mime)
                if mime_error:
                    if "危险" in mime_error:
                        raise HTTPException(status_code=400, detail=mime_error)
                    logger.warning(mime_error)
            except HTTPException:
                raise

        if resource_type == "other":
            resource_type = _auto_detect_resource_type(file.filename, file_ext)

        project_upload_dir = os.path.join(settings.UPLOAD_DIR, str(project_id))
        os.makedirs(project_upload_dir, exist_ok=True)

        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(project_upload_dir, unique_filename)

        with open(file_path, "wb") as f:
            f.write(contents)
        saved_file_path = file_path

        file_size = get_file_size(file_path)

        db_iteration_id = iteration_id if iteration_id and iteration_id > 0 else None

        def _create_file(sync_db: Session) -> ProjectFile:
            return file_crud.create_project_file(
                db=sync_db,
                project_id=project_id,
                file_name=file.filename,
                file_type=file_ext,
                file_url=file_path,
                file_source="file",
                size=file_size,
                resource_type=resource_type,
                description=description,
                iteration_id=db_iteration_id,
            )

        sync_db = PrimarySessionLocal()
        try:
            new_file = await asyncio.to_thread(_create_file, sync_db)
        finally:
            sync_db.close()

        return {
            "code": 200,
            "message": "上传成功",
            "data": _file_to_dict(new_file),
        }
    except HTTPException:
        raise
    except Exception:
        if saved_file_path and os.path.exists(saved_file_path):
            try:
                os.remove(saved_file_path)
                logger.info(f"已清理失败的文件: {saved_file_path}")
            except OSError as cleanup_error:
                logger.warning(f"清理文件失败: {cleanup_error}")
        raise HTTPException(status_code=500, detail="上传文件失败")


@router.post("/submit-url", response_model=ApiResponse)
async def submit_url(
    url_request: UrlSubmitRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=410, detail="URL提交功能已弃用，请使用文件上传"
    )


@router.post("/update-sort")
async def update_file_sort(
    file_ids: List[int] = Body(..., description="文件ID列表（按新顺序排列）"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if not file_ids or len(file_ids) == 0:
            raise HTTPException(status_code=400, detail="文件ID列表不能为空")

        if len(file_ids) > 100:
            raise HTTPException(
                status_code=400, detail="单次更新数量不能超过100个"
            )

        unique_file_ids = list(dict.fromkeys(file_ids))

        # 查询用户拥有的项目ID集合（参数化批量查询，杜绝SQL注入）
        project_result = await db.execute(
            select(Project.id).where(Project.user_id == current_user.id)
        )
        user_project_ids = set(project_result.scalars().all())

        # 批量查询所有文件记录，避免循环内逐条查询（N+1 修复）
        file_result = await db.execute(
            select(ProjectFile).where(
                ProjectFile.id.in_(unique_file_ids),
                ProjectFile.is_active.is_(True),
            )
        )
        file_records = file_result.scalars().all()
        file_map = {record.id: record for record in file_records}

        updated_count = 0
        for index, file_id in enumerate(unique_file_ids):
            file_record = file_map.get(file_id)

            if file_record and file_record.project_id in user_project_ids:
                file_record.sort_order = index + 1
                updated_count += 1

        await db.commit()

        logger.info(
            (
                f"更新文件排序: 用户={current_user.username}, "
                f"更新{updated_count}/{len(unique_file_ids)}个"
            )
        )

        return {
            "code": 200,
            "message": f"成功更新 {updated_count} 个文件的排序",
            "data": {"updated_count": updated_count},
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新排序失败: {e}")
        raise HTTPException(status_code=500, detail="更新排序失败")
