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

from dataclasses import dataclass

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db, PrimarySessionLocal
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.file import ResourceType
from app.crud import file as file_crud
from app.core.config import settings
import asyncio
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


async def _execute(db: Session, stmt):
    """同步 Session 的查询在线程池执行，避免阻塞事件循环（R2-1）。"""
    return await asyncio.to_thread(db.execute, stmt)


router = APIRouter()


@dataclass(frozen=True)
class _BatchUploadContext:
    """批量上传的请求级上下文（避免 helper 参数膨胀）。"""

    project_id: int
    project_upload_dir: str
    resource_type: str
    description: str
    name: str
    iteration_id: int | None


def _validate_batch_request(resource_type: str, files: list[UploadFile]) -> None:
    """校验资源类型白名单与文件数量上限。"""
    valid_resource_types = [e.value for e in ResourceType]
    if resource_type not in valid_resource_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的资源类型，允许值: {', '.join(valid_resource_types)}",
        )
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一个文件")
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="单次最多上传20个文件")


def _check_mime_risk(contents: bytes, file_ext: str, resource_type: str) -> str | None:
    """MIME 探测：返回阻断原因；非阻断告警或探测异常返回 None。"""
    if not (_MAGIC_AVAILABLE and _magic_module is not None):
        return None
    try:
        detected_mime = _magic_module.from_buffer(contents, mime=True)
        mime_error = validate_file_mime(file_ext, detected_mime)
        if not mime_error:
            return None
        if "危险" in mime_error:
            return mime_error
        if "压缩包" in mime_error and not (file_ext in ARCHIVE_EXTENSIONS and resource_type == "ui_mockup"):
            return mime_error
        logger.warning(mime_error)
    except Exception:
        logger.debug("文件MIME校验异常", exc_info=True)
    return None


async def _prepare_batch_file(
    file: UploadFile, allowed_extensions: list[str], resource_type: str
) -> tuple[str | None, bytes | None, dict | None]:
    """逐项校验单文件；被拒绝时返回失败项（file_ext / contents 为 None）。"""
    if not file.filename:
        return None, None, {"file_name": "未知文件", "reason": "文件名不能为空"}

    file_ext = validate_file_format(file.filename)
    if not file_ext:
        return None, None, {"file_name": file.filename, "reason": "不支持的文件格式"}

    if allowed_extensions and file_ext.lower() not in [e.lower().lstrip(".") for e in allowed_extensions]:
        return None, None, {"file_name": file.filename, "reason": f"不允许的文件类型: .{file_ext}"}

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE:
        max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        return None, None, {"file_name": file.filename, "reason": f"文件过大，最大允许 {max_size_mb}MB"}

    mime_reason = _check_mime_risk(contents, file_ext, resource_type)
    if mime_reason:
        return None, None, {"file_name": file.filename, "reason": mime_reason}
    return file_ext, contents, None


async def _store_archive_file(
    file: UploadFile,
    file_ext: str,
    contents: bytes,
    ctx: _BatchUploadContext,
    file_resource_type: str,
) -> tuple[list[dict], list[dict]]:
    """落盘压缩包、解压导入 UI 原型图片，成功与失败均返回明细。"""
    zip_path = os.path.join(ctx.project_upload_dir, f"{uuid.uuid4()}.{file_ext}")
    with open(zip_path, "wb") as f:
        f.write(contents)

    def _extract_zip(sync_db: Session) -> tuple:
        return _extract_images_from_zip(
            zip_path=zip_path,
            project_upload_dir=ctx.project_upload_dir,
            project_id=ctx.project_id,
            resource_type=file_resource_type,
            description=ctx.description,
            db=sync_db,
            zip_filename=file.filename,
            name=ctx.name,
            iteration_id=ctx.iteration_id,
        )

    zip_sync_db = PrimarySessionLocal()
    try:
        zip_uploaded, zip_failed = await asyncio.to_thread(_extract_zip, zip_sync_db)
    finally:
        zip_sync_db.close()

    try:
        os.remove(zip_path)
    except Exception:
        logger.debug("删除临时zip文件失败", exc_info=True)
    return zip_uploaded, zip_failed


async def _store_batch_file(
    file: UploadFile,
    file_ext: str,
    contents: bytes,
    file_index: int,
    ctx: _BatchUploadContext,
) -> tuple[list[dict], list[dict], bool]:
    """落盘并入库单文件；返回（成功项, 失败项, 是否占用序号）。"""
    file_resource_type = ctx.resource_type
    if ctx.resource_type == "other":
        file_resource_type = _auto_detect_resource_type(file.filename, file_ext)

    if file_ext in ARCHIVE_EXTENSIONS and ctx.resource_type == "ui_mockup":
        uploaded, failed = await _store_archive_file(file, file_ext, contents, ctx, file_resource_type)
        return uploaded, failed, False

    file_path = os.path.join(ctx.project_upload_dir, f"{uuid.uuid4()}.{file_ext}")
    with open(file_path, "wb") as f:
        f.write(contents)

    file_size = get_file_size(file_path)
    display_name = f"{ctx.name} ({file_index})" if ctx.name else file.filename
    db_iteration_id = ctx.iteration_id if ctx.iteration_id and ctx.iteration_id > 0 else None

    def _create_file(sync_db: Session):
        return file_crud.create_project_file(
            db=sync_db,
            project_id=ctx.project_id,
            file_name=display_name,
            file_type=file_ext,
            file_url=file_path,
            file_source="file",
            size=file_size,
            resource_type=file_resource_type,
            description=ctx.description,
            iteration_id=db_iteration_id,
        )

    file_sync_db = PrimarySessionLocal()
    try:
        new_file = await asyncio.to_thread(_create_file, file_sync_db)
    finally:
        file_sync_db.close()

    return [_file_to_dict(new_file)], [], True


@router.post("/batch-upload", response_model=ApiResponse)
async def batch_upload_files(
    project_id: int = Form(...),
    files: list[UploadFile] = File(...),
    resource_type: str = Form("other"),
    description: str = Form(""),
    name: str = Form(""),
    iteration_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _validate_batch_request(resource_type, files)

        project_result = await _execute(
            db, select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
        )
        project = project_result.scalars().first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目",
            )

        allowed_extensions = settings.allowed_extensions_list
        project_upload_dir = os.path.join(settings.UPLOAD_DIR, str(project_id))
        os.makedirs(project_upload_dir, exist_ok=True)

        ctx = _BatchUploadContext(
            project_id=project_id,
            project_upload_dir=project_upload_dir,
            resource_type=resource_type,
            description=description,
            name=name,
            iteration_id=iteration_id,
        )

        uploaded_files = []
        failed_files = []
        file_index = 1

        for file in files:
            try:
                file_ext, contents, failure = await _prepare_batch_file(file, allowed_extensions, resource_type)
                if failure is not None:
                    failed_files.append(failure)
                    continue

                stored, fails, occupies_index = await _store_batch_file(file, file_ext, contents, file_index, ctx)
                uploaded_files.extend(stored)
                failed_files.extend(fails)
                if occupies_index:
                    file_index += 1
            except Exception as e:
                logger.error(f"批量上传-单文件处理失败: {file.filename}, 错误: {str(e)}")
                failed_files.append({"file_name": file.filename, "reason": str(e)})

        logger.info(f"批量上传完成: 用户={current_user.username}, 成功={len(uploaded_files)}, 失败={len(failed_files)}")

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
