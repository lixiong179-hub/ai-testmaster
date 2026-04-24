"""
文件批量上传端点模块

本模块定义批量文件上传的API端点，支持一次上传多个文件。

路由前缀: /file（由父模块file.py注册）
标签: 文件管理

端点概览:
    - POST /batch-upload - 批量上传文件

权限要求: 需要Bearer令牌认证

业务说明:
    - 批量上传支持多个文件同时提交
    - 每个文件独立处理，部分失败不影响其他文件
"""

from fastapi import APIRouter
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.file import ResourceType
from app.crud import file as file_crud
from app.core.config import settings
import uuid
import os
from app.utils.file_utils import (
    validate_file_format,
    get_file_size,
    validate_file_mime,
    ARCHIVE_EXTENSIONS,
)
from app.api.v1.endpoints.file_upload import (
    _auto_detect_resource_type,
    _file_to_dict,
    _MAGIC_AVAILABLE,
)
try:
    import magic as _magic_module
except ImportError:
    _magic_module = None
from app.api.v1.endpoints.file_export import _extract_images_from_zip
from loguru import logger

router = APIRouter()


@router.post("/batch-upload", response_model=dict)
async def batch_upload_files(
    project_id: int = Form(...),
    files: List[UploadFile] = File(...),
    resource_type: str = Form("ui_mockup"),
    description: str = Form(""),
    name: str = Form(""),
    iteration_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        valid_resource_types = [e.value for e in ResourceType]
        if resource_type not in valid_resource_types:
            raise HTTPException(
                status_code=400,
                detail=f"无效的资源类型，允许值: {', '.join(valid_resource_types)}",
            )

        project = (
            db.query(Project)
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

        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="请选择至少一个文件")

        if len(files) > 20:
            raise HTTPException(status_code=400, detail="单次最多上传20个文件")

        allowed_extensions = settings.allowed_extensions_list
        project_upload_dir = os.path.join(settings.UPLOAD_DIR, str(project_id))
        os.makedirs(project_upload_dir, exist_ok=True)

        uploaded_files = []
        failed_files = []
        file_index = 1

        for file in files:
            try:
                if not file.filename:
                    failed_files.append(
                        {"file_name": "未知文件", "reason": "文件名不能为空"}
                    )
                    continue

                file_ext = validate_file_format(file.filename)
                if not file_ext:
                    failed_files.append(
                        {
                            "file_name": file.filename,
                            "reason": "不支持的文件格式",
                        }
                    )
                    continue

                if allowed_extensions and file_ext.lower() not in [
                    e.lower().lstrip(".") for e in allowed_extensions
                ]:
                    failed_files.append(
                        {
                            "file_name": file.filename,
                            "reason": f"不允许的文件类型: .{file_ext}",
                        }
                    )
                    continue

                contents = await file.read()
                if len(contents) > settings.MAX_UPLOAD_SIZE:
                    max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
                    failed_files.append(
                        {
                            "file_name": file.filename,
                            "reason": f"文件过大，最大允许 {max_size_mb}MB",
                        }
                    )
                    continue

                if _MAGIC_AVAILABLE and _magic_module is not None:
                    try:
                        detected_mime = _magic_module.from_buffer(contents, mime=True)
                        mime_error = validate_file_mime(
                            file_ext, detected_mime
                        )
                        if mime_error:
                            if "危险" in mime_error:
                                failed_files.append(
                                    {
                                        "file_name": file.filename,
                                        "reason": mime_error,
                                    }
                                )
                                continue
                            if "压缩包" in mime_error and not (
                                file_ext in ARCHIVE_EXTENSIONS
                                and resource_type == "ui_mockup"
                            ):
                                failed_files.append(
                                    {
                                        "file_name": file.filename,
                                        "reason": mime_error,
                                    }
                                )
                                continue
                            logger.warning(mime_error)
                    except Exception:
                        pass

                file_resource_type = resource_type
                if resource_type == "other":
                    file_resource_type = _auto_detect_resource_type(
                        file.filename, file_ext
                    )

                if (
                    file_ext in ARCHIVE_EXTENSIONS
                    and resource_type == "ui_mockup"
                ):
                    unique_filename = f"{uuid.uuid4()}.{file_ext}"
                    zip_path = os.path.join(
                        project_upload_dir, unique_filename
                    )

                    with open(zip_path, "wb") as f:
                        f.write(contents)

                    zip_uploaded, zip_failed = _extract_images_from_zip(
                        zip_path=zip_path,
                        project_upload_dir=project_upload_dir,
                        project_id=project_id,
                        resource_type=file_resource_type,
                        description=description,
                        db=db,
                        zip_filename=file.filename,
                        name=name,
                        iteration_id=iteration_id,
                    )

                    uploaded_files.extend(zip_uploaded)
                    failed_files.extend(zip_failed)

                    try:
                        os.remove(zip_path)
                    except Exception:
                        pass

                    continue

                unique_filename = f"{uuid.uuid4()}.{file_ext}"
                file_path = os.path.join(project_upload_dir, unique_filename)

                with open(file_path, "wb") as f:
                    f.write(contents)

                file_size = get_file_size(file_path)

                if name:
                    display_name = f"{name} ({file_index})"
                else:
                    display_name = file.filename

                db_iteration_id = (
                    None
                    if (iteration_id is None or iteration_id <= 0)
                    else iteration_id
                )
                new_file = file_crud.create_project_file(
                    db=db,
                    project_id=project_id,
                    file_name=display_name,
                    file_type=file_ext,
                    file_url=file_path,
                    file_source="file",
                    size=file_size,
                    resource_type=file_resource_type,
                    description=description,
                    iteration_id=db_iteration_id,
                )

                uploaded_files.append(_file_to_dict(new_file))
                file_index += 1
            except Exception as e:
                logger.error(
                    f"批量上传-单文件处理失败: {file.filename}, 错误: {str(e)}"
                )
                failed_files.append(
                    {"file_name": file.filename, "reason": str(e)}
                )

        logger.info(
            f"批量上传完成: 用户={current_user.username}, "
            f"成功={len(uploaded_files)}, 失败={len(failed_files)}"
        )

        return {
            "code": 200,
            "message": f"批量上传完成，成功 {len(uploaded_files)} 个"
            + (f"，失败 {len(failed_files)} 个" if failed_files else ""),
            "data": {
                "uploaded_files": uploaded_files,
                "failed_files": failed_files,
                "success_count": len(uploaded_files),
                "fail_count": len(failed_files),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量上传失败: {e}")
        raise HTTPException(status_code=500, detail="批量上传失败")
