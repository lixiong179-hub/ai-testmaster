"""跨设备用例迁移API端点。"""
import os
import tempfile
import threading
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.database import async_get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.project import Project
from app.core.exception import create_response
from app.core.config import settings
from app.schemas.common import ApiResponse
from app.services.case_migration import CaseMigrationService
from app.services.test_case_view import TestCaseViewService

router = APIRouter(prefix="/case-migration", tags=["跨设备用例迁移"])

VALID_DEVICES = {"tablet", "phone", "desktop", "web"}


class BatchMigrationPreviewRequest(BaseModel):
    source_case_ids: list[int] = Field(..., min_length=1, description="源用例ID列表")
    target_device: str = Field(..., description="目标设备类型")
    target_project_id: int = Field(..., ge=1, description="目标项目ID")
    source_device: str = Field("tablet", description="源设备类型")
    target_ui_specs: str = Field("", description="目标设备UI规格描述")


class BatchMigrationCommitRequest(BaseModel):
    batch_id: str = Field(..., min_length=1, description="迁移批次ID")
    target_project_id: int = Field(..., ge=1, description="目标项目ID")
    target_device: str = Field(..., description="目标设备类型")
    items: list[dict] = Field(..., min_length=1, description="预览项")

_ai_client_instance = None
_ai_client_lock = threading.Lock()


def _get_ai_client():
    """获取 AI 客户端单例。

    使用 app.ai.openai_client.OpenAIClient（实现 AIClient Protocol 的 complete 方法）。
    通过 settings 配置 API 密钥与端点，实例化本身不发起网络请求（懒加载）。
    """
    global _ai_client_instance
    if _ai_client_instance is not None:
        return _ai_client_instance
    with _ai_client_lock:
        if _ai_client_instance is not None:
            return _ai_client_instance
        try:
            from app.ai.openai_client import OpenAIClient
            _ai_client_instance = OpenAIClient()
            return _ai_client_instance
        except Exception as exc:
            logger.error(f"OpenAIClient 初始化失败: {exc}")
            return None


def _validate_device_pair(source_device: str, target_device: str) -> None:
    if source_device not in VALID_DEVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的源设备类型: {source_device}，合法值: {', '.join(sorted(VALID_DEVICES))}",
        )
    if target_device not in VALID_DEVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的目标设备类型: {target_device}，合法值: {', '.join(sorted(VALID_DEVICES))}",
        )
    if source_device == target_device:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"源设备与目标设备相同({source_device})，无需迁移",
        )


async def _verify_target_project(
    db: AsyncSession, target_project_id: int, current_user: User
) -> None:
    stmt = select(Project).where(
        Project.id == target_project_id,
        Project.user_id == current_user.id,
    )
    target_project = (await db.execute(stmt)).scalar_one_or_none()
    if not target_project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此目标项目或项目不存在",
        )


def _remove_temp_file(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    try:
        os.unlink(path)
    except OSError as exc:
        logger.warning(f"临时文件清理失败: {path}, error={exc}")


@router.post("/normalize-excel", response_model=ApiResponse, summary="Excel格式规范化预处理")
async def normalize_excel(
    file: UploadFile = File(..., description="Excel文件"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持.xlsx或.xls格式的Excel文件",
        )
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            content = await file.read()
            if len(content) > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"文件大小超过限制({settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB)",
                )
            tmp.write(content)
            temp_path = tmp.name

        def _normalize(sync_db):
            service = TestCaseViewService(sync_db)
            return service.normalize_excel(temp_path)
        result = await db.run_sync(_normalize)
        return create_response(data=result)
    except Exception as e:
        logger.error(f"Excel规范化检测失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检测失败: {e}",
        )
    finally:
        _remove_temp_file(temp_path)


@router.post("/import-excel", response_model=ApiResponse, summary="导入Excel用例（支持设备类型标记）")
async def import_excel(
    file: UploadFile = File(..., description="Excel文件"),
    project_id: int = Form(..., description="项目ID"),
    target_device: Optional[str] = Form(None, description="目标设备类型：tablet/phone/desktop/web"),
    iteration_id: Optional[int] = Form(None, description="迭代ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持.xlsx或.xls格式的Excel文件",
        )
    if target_device and target_device not in VALID_DEVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的设备类型: {target_device}，合法值: {', '.join(sorted(VALID_DEVICES))}",
        )
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            content = await file.read()
            if len(content) > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"文件大小超过限制({settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB)",
                )
            tmp.write(content)
            temp_path = tmp.name

        def _import(sync_db):
            service = TestCaseViewService(sync_db)
            functional_result = service.validate_functional_excel(temp_path)
            imported_ids: list = []
            if functional_result.get("valid"):
                imported_ids = service.import_functional_excel(
                    temp_path, project_id, target_device=target_device, iteration_id=iteration_id,
                )
            else:
                standard_result = service.validate_excel_format(temp_path)
                if standard_result.get("valid"):
                    case_id = service.import_from_excel(
                        temp_path, project_id, target_device=target_device, iteration_id=iteration_id,
                    )
                    imported_ids = [case_id] if case_id else []
                else:
                    all_errors = functional_result.get("errors", []) + standard_result.get("errors", [])
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Excel格式验证失败: {all_errors}",
                    )
            return imported_ids

        imported_ids = await db.run_sync(_import)
        if not imported_ids:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="导入失败，未成功导入任何用例",
            )
        return create_response(data={
            "imported_count": len(imported_ids),
            "imported_case_ids": imported_ids,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excel导入失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入失败: {e}",
        )
    finally:
        _remove_temp_file(temp_path)


@router.post("/migrate-single", response_model=ApiResponse, summary="单条用例跨设备迁移")
async def migrate_single_case(
    source_case_id: int = Form(..., description="源用例ID"),
    target_device: str = Form(..., description="目标设备类型：tablet/phone/desktop/web"),
    target_project_id: int = Form(..., description="目标项目ID"),
    source_device: str = Form("tablet", description="源设备类型"),
    target_ui_specs: Optional[str] = Form(None, description="目标设备UI规格描述"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _validate_device_pair(source_device, target_device)
    await _verify_target_project(db, target_project_id, current_user)
    try:
        service = CaseMigrationService(db)
        result = await service.migrate_single_case(
            source_case_id=source_case_id,
            target_device=target_device,
            target_project_id=target_project_id,
            source_device=source_device,
            target_ui_specs=target_ui_specs or "",
            ai_client=_get_ai_client(),
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "迁移失败"),
            )
        return create_response(data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"单条用例迁移失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"迁移失败: {e}",
        )


@router.post("/preview-batch", response_model=ApiResponse, summary="批量用例跨设备迁移预览")
async def preview_batch_migration(
    body: BatchMigrationPreviewRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    _validate_device_pair(body.source_device, body.target_device)
    await _verify_target_project(db, body.target_project_id, current_user)
    service = CaseMigrationService(db)
    result = await service.preview_batch(
        source_case_ids=body.source_case_ids,
        target_device=body.target_device,
        target_project_id=body.target_project_id,
        source_device=body.source_device,
        target_ui_specs=body.target_ui_specs,
        ai_client=_get_ai_client(),
    )
    return create_response(data=result)


@router.post("/commit-batch", response_model=ApiResponse, summary="确认批量迁移并入库")
async def commit_batch_migration(
    body: BatchMigrationCommitRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _verify_target_project(db, body.target_project_id, current_user)
    if body.target_device not in VALID_DEVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的目标设备类型: {body.target_device}",
        )
    items = []
    for item in body.items:
        normalized = dict(item)
        normalized["batch_id"] = body.batch_id
        items.append(normalized)
    result = await CaseMigrationService(db).commit_batch(
        preview_items=items,
        target_project_id=body.target_project_id,
        target_device=body.target_device,
    )
    return create_response(data=result)


@router.get("/batches/{batch_id}", response_model=ApiResponse, summary="查询迁移批次")
async def get_migration_batch(
    batch_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await CaseMigrationService(db).get_batch_cases(batch_id)
    return create_response(data=result)


@router.post("/batches/{batch_id}/rollback", response_model=ApiResponse, summary="回滚迁移批次")
async def rollback_migration_batch(
    batch_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await CaseMigrationService(db).rollback_batch(batch_id)
    return create_response(data=result)
