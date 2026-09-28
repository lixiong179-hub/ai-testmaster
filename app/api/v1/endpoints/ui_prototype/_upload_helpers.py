"""UI 原型上传端点的文件保存与项目权限 helper。

从 screen_endpoints.py 拆出，封装上传文件保存循环、迭代过滤条件构建，
以及 async 版本的项目权限校验，便于独立测试与复用。
"""
import os
import shutil
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.api.v1.endpoints.ui_prototype.helpers import (
    _sanitize_filename_component,
    _validate_image_file,
)
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen


def _apply_iteration_filter_stmt(stmt: Select, iteration_id: Optional[int]) -> Select:
    """async 风格的迭代过滤条件构建器，用于 select 语句链式构建。

    与 crud/ui_prototype_screen._apply_iteration_filter 同义，但作用在 select 对象上。
    """
    if iteration_id is not None:
        if iteration_id <= 0:
            stmt = stmt.outerjoin(
                UIPrototypeProject,
                UIPrototypeScreen.prototype_project_id == UIPrototypeProject.id,
            ).where(
                or_(
                    UIPrototypeProject.iteration_id.is_(None),
                    UIPrototypeScreen.prototype_project_id.is_(None),
                )
            )
        else:
            stmt = stmt.join(
                UIPrototypeProject,
                UIPrototypeScreen.prototype_project_id == UIPrototypeProject.id,
            ).where(UIPrototypeProject.iteration_id == iteration_id)
    return stmt


def _save_uploaded_files(
    project_dir: str,
    project_dir_abs: str,
    safe_prototype_name: str,
    files: list,
) -> tuple[list[dict], list[dict]]:
    """保存上传文件到 project_dir，返回 (saved_files, invalid_files)。

    saved_files: [{"path", "name", "size"}]
    invalid_files: [{"name", "error"}]
    """
    saved_files: list[dict] = []
    invalid_files: list[dict] = []
    for i, file in enumerate(files):
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        ext = (
            os.path.splitext(file.filename)[1] if file.filename else ".png"
        )
        filename = f"{safe_prototype_name}_{timestamp}_{i}{ext}"
        filepath = os.path.join(project_dir, filename)
        # 防御性兜底：验证最终路径仍在 project_dir 内
        if not os.path.abspath(filepath).startswith(project_dir_abs + os.sep):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名包含非法字符",
            )

        try:
            with open(filepath, "wb") as f:
                shutil.copyfileobj(file.file, f)
        finally:
            if hasattr(file, 'file') and hasattr(file.file, 'close'):
                file.file.close()

        file_size = os.path.getsize(filepath)

        is_valid, error_msg = _validate_image_file(filepath)
        if not is_valid:
            logger.warning(f"图片验证失败: {filename}, 原因: {error_msg}")
            invalid_files.append({"name": file.filename or filename, "error": error_msg})
            try:
                os.remove(filepath)
            except OSError:
                logger.debug("删除无效图片文件失败")
            continue

        saved_files.append(
            {
                "path": filepath,
                "name": file.filename or filename,
                "size": file_size,
            }
        )
    return saved_files, invalid_files


async def _verify_project_owner_async(
    db: AsyncSession,
    project_id: int,
    user_id: int,
) -> Project:
    """async 版本项目权限校验。不存在或无权限则抛 403。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    return project


__all__ = [
    "_apply_iteration_filter_stmt",
    "_save_uploaded_files",
    "_verify_project_owner_async",
]
