"""
文件导出端点模块

本模块定义文件导出的API端点，支持将测试数据导出为不同格式。

路由前缀: /file（由父模块file.py注册）
标签: 文件管理

端点概览:
    - GET /{file_id}/download - 下载文件
    - POST /export-excel     - 导出Excel格式

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 下载文件返回原始文件流
    - Excel导出支持按项目筛选数据
"""
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import FileResponse
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.models.project import Project, ProjectFile
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.file import FileExtractRequest
from app.services.file_content_extractor import batch_extract_files
from app.core.config import settings
import uuid
import zipfile
import os
from app.utils.file_utils import (
    get_file_size,
)
from app.crud import file as file_crud
from app.api.v1.endpoints.file_upload import _file_to_dict
from loguru import logger

router = APIRouter()

SUPPORTED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

MAX_ZIP_ENTRIES = settings.MAX_ZIP_ENTRIES
MAX_ZIP_TOTAL_SIZE = settings.MAX_ZIP_TOTAL_SIZE


def _extract_images_from_zip(
    zip_path: str,
    project_upload_dir: str,
    project_id: int,
    resource_type: str,
    description: str,
    db: Session,
    zip_filename: str,
    name: str = "",
    iteration_id: Optional[int] = None,
) -> tuple:
    uploaded_files = []
    failed_files = []

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            total_size = 0
            entries = [info for info in zf.infolist() if not info.is_dir()]

            if len(entries) > MAX_ZIP_ENTRIES:
                failed_files.append(
                    {
                        "file_name": zip_filename,
                        "reason": f"ZIP包内文件数超过限制（最多{MAX_ZIP_ENTRIES}个）",
                    }
                )
                return uploaded_files, failed_files

            safe_entries = []
            for info in entries:
                if info.filename.startswith("/") or ".." in info.filename:
                    failed_files.append(
                        {
                            "file_name": os.path.basename(info.filename)
                            or "未知文件",
                            "reason": "文件路径包含非法字符",
                        }
                    )
                    continue
                safe_entries.append(info)

            for info in safe_entries:
                basename = os.path.basename(info.filename)
                if not basename:
                    continue
                file_ext = (
                    basename.rsplit(".", 1)[-1].lower()
                    if "." in basename
                    else ""
                )
                if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                    total_size += info.file_size

            if total_size > MAX_ZIP_TOTAL_SIZE:
                failed_files.append(
                    {
                        "file_name": zip_filename,
                        "reason": (
                            f"ZIP包中图片总大小超过限制"
                            f"（最大{MAX_ZIP_TOTAL_SIZE // (1024 * 1024)}MB）"
                        ),
                    }
                )
                return uploaded_files, failed_files

            image_index = 1
            for info in safe_entries:
                basename = os.path.basename(info.filename)
                if not basename:
                    continue

                file_ext = (
                    basename.rsplit(".", 1)[-1].lower()
                    if "." in basename
                    else ""
                )

                if file_ext not in SUPPORTED_IMAGE_EXTENSIONS:
                    continue

                try:
                    if info.file_size > settings.MAX_UPLOAD_SIZE:
                        max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
                        failed_files.append(
                            {
                                "file_name": basename,
                                "reason": f"文件过大，最大允许 {max_size_mb}MB",
                            }
                        )
                        continue

                    with zf.open(info) as src:
                        file_contents = src.read()

                    unique_filename = f"{uuid.uuid4()}.{file_ext}"
                    file_path = os.path.join(
                        project_upload_dir, unique_filename
                    )

                    with open(file_path, "wb") as dst:
                        dst.write(file_contents)

                    file_size = get_file_size(file_path)

                    if name:
                        display_name = f"{name} ({image_index})"
                    else:
                        display_name = basename

                    db_iteration_id = iteration_id if iteration_id and iteration_id > 0 else None
                    new_file = file_crud.create_project_file(
                        db=db,
                        project_id=project_id,
                        file_name=display_name,
                        file_type=file_ext,
                        file_url=file_path,
                        file_source="file",
                        size=file_size,
                        resource_type=resource_type,
                        description=description,
                        iteration_id=db_iteration_id,
                    )

                    uploaded_files.append(_file_to_dict(new_file))
                    image_index += 1
                except Exception as e:
                    logger.error(
                        f"ZIP解压-单文件处理失败: {basename}, 错误: {str(e)}"
                    )
                    failed_files.append(
                        {"file_name": basename, "reason": str(e)}
                    )

    except zipfile.BadZipFile:
        failed_files.append(
            {"file_name": zip_filename, "reason": "无效的ZIP文件"}
        )
    except Exception as e:
        logger.error(f"ZIP解压失败: {str(e)}")
        failed_files.append(
            {"file_name": zip_filename, "reason": f"ZIP解压失败: {str(e)}"}
        )

    return uploaded_files, failed_files


@router.post("/extract-content", response_model=ApiResponse)
async def extract_file_content(
    extract_request: FileExtractRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _check_and_extract(sync_db: Session) -> dict:
            project = (
                sync_db.query(Project)
                .filter(
                    Project.id == extract_request.project_id,
                    Project.user_id == current_user.id,
                )
                .first()
            )

            if not project:
                raise HTTPException(status_code=403, detail="无权限操作此项目")

            import asyncio
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    batch_extract_files(
                        extract_request.file_ids, sync_db, extract_request.force_refresh
                    )
                )
            finally:
                loop.close()

        results = await db.run_sync(_check_and_extract)

        return {"code": 200, "message": "提取任务已启动", "data": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取文件内容失败: {e}")
        raise HTTPException(
            status_code=500, detail="提取文件内容失败"
        )


@router.get("/preview/{file_id}")
async def preview_file(
    file_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get_file(sync_db: Session) -> str:
        file_record = (
            sync_db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
        )
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")

        project = (
            sync_db.query(Project)
            .filter(
                Project.id == file_record.project_id,
                Project.user_id == current_user.id,
            )
            .first()
        )
        if not project:
            raise HTTPException(status_code=403, detail="无权访问此文件")

        file_path = file_record.file_url
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        return file_path

    file_path = await db.run_sync(_get_file)
    return FileResponse(path=file_path)


@router.get("/preview-screen/{screen_id}")
async def preview_screen(
    screen_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get_screen_file(sync_db: Session) -> str:
        from app.models.ui_prototype import UIPrototypeScreen

        screen = (
            sync_db.query(UIPrototypeScreen)
            .filter(UIPrototypeScreen.id == screen_id)
            .first()
        )
        if not screen:
            raise HTTPException(status_code=404, detail="屏幕不存在")

        project = (
            sync_db.query(Project)
            .filter(
                Project.id == screen.project_id, Project.user_id == current_user.id
            )
            .first()
        )
        if not project:
            raise HTTPException(status_code=403, detail="无权访问此文件")

        file_path = screen.original_file_path
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")

        return file_path

    file_path = await db.run_sync(_get_screen_file)
    return FileResponse(path=file_path)
