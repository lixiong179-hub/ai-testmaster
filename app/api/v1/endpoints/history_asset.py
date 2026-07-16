import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.history_asset import HistoryAsset
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.history_asset import (
    HistoryClassificationResponse,
    HistoryClassificationSummary,
)
from app.api.v1.endpoints._history_asset_helpers import (
    _asset_to_detail_response,
    _asset_to_upload_response,
    _validate_project_permission,
)
from app.api.v1.endpoints._history_asset_parsers import (
    _parse_excel_cases,
    _parse_xmind_cases,
)
from app.api.v1.endpoints._history_asset_classification import _classify_history_cases

router = APIRouter(tags=["历史资产"])

UPLOAD_DIR = "uploads/history_assets"

_ALLOWED_ASSET_TYPES = {"excel", "xmind", "system_cases"}
_ALLOWED_EXCEL_EXTS = {".xlsx", ".xls"}
_ALLOWED_XMIND_EXTS = {".xmind"}


@router.post("/upload")
async def upload_history_asset(
    project_id: int = Form(...),
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _check_permission(sync_db: Session) -> Project:
        return _validate_project_permission(project_id, current_user.id, sync_db)

    await db.run_sync(_check_permission)

    if asset_type not in _ALLOWED_ASSET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资产类型: {asset_type}，允许: {', '.join(sorted(_ALLOWED_ASSET_TYPES))}",
        )

    filename = file.filename or "unknown"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if asset_type == "excel" and ext not in _ALLOWED_EXCEL_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Excel 资产仅支持: {', '.join(sorted(_ALLOWED_EXCEL_EXTS))}",
        )
    if asset_type == "xmind" and ext not in _ALLOWED_XMIND_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"XMind 资产仅支持: {', '.join(sorted(_ALLOWED_XMIND_EXTS))}",
        )

    upload_dir = os.path.join(UPLOAD_DIR, str(project_id))
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, unique_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    parsed_cases: list[dict[str, Any]] = []
    parse_error = None
    parse_status = "completed"

    try:
        if asset_type == "excel":
            parsed_cases = _parse_excel_cases(file_path)
        elif asset_type == "xmind":
            parsed_cases = _parse_xmind_cases(file_path)
    except ValueError as e:
        parse_status = "failed"
        parse_error = str(e)[:500]
        logger.warning(f"历史资产解析失败: {e}")

    final_parse_status = parse_status
    final_parse_error = parse_error
    final_parsed_cases = parsed_cases if parse_status == "completed" else None
    final_case_count = len(parsed_cases) if parse_status == "completed" else 0

    def _create_asset(sync_db: Session) -> HistoryAsset:
        asset = HistoryAsset(
            project_id=project_id,
            user_id=current_user.id,
            asset_type=asset_type,
            file_path=file_path,
            original_filename=filename,
            parse_status=final_parse_status,
            parse_error=final_parse_error,
            parsed_cases_json=final_parsed_cases,
            case_count=final_case_count,
        )
        sync_db.add(asset)
        sync_db.commit()
        sync_db.refresh(asset)
        return asset

    asset = await db.run_sync(_create_asset)

    return create_response(data=_asset_to_upload_response(asset))


@router.get("")
async def list_history_assets(
    project_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _list(sync_db: Session) -> tuple:
        _validate_project_permission(project_id, current_user.id, sync_db)
        query = sync_db.query(HistoryAsset).filter(
            HistoryAsset.project_id == project_id
        )
        total = query.count()
        skip = (page - 1) * page_size
        assets = (
            query.order_by(HistoryAsset.created_at.desc())
            .offset(skip)
            .limit(page_size)
            .all()
        )
        return assets, total

    assets, total = await db.run_sync(_list)
    items = [_asset_to_upload_response(a) for a in assets]
    return create_response(
        data={"items": items, "total": total, "page": page, "page_size": page_size}
    )


@router.post("/align")
async def align_history_assets(
    project_id: int = Form(...),
    history_asset_ids: str = Form(...),
    requirement_file_ids: str | None = Form(None),
    test_point_ids: str | None = Form(None),
    ui_screen_ids: str | None = Form(None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    import json

    try:
        asset_ids = json.loads(history_asset_ids)
        req_file_ids = json.loads(requirement_file_ids) if requirement_file_ids else None
        tp_ids = json.loads(test_point_ids) if test_point_ids else None
        ui_ids = json.loads(ui_screen_ids) if ui_screen_ids else None
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"参数 JSON 解析失败: {e}",
        ) from e

    def _align(sync_db: Session) -> dict:
        _validate_project_permission(project_id, current_user.id, sync_db)

        assets = (
            sync_db.query(HistoryAsset)
            .filter(
                HistoryAsset.id.in_(asset_ids),
                HistoryAsset.project_id == project_id,
            )
            .all()
        )
        if len(assets) != len(asset_ids):
            found_ids = {a.id for a in assets}
            missing = set(asset_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"以下历史资产不存在或不属于当前项目: {sorted(missing)}",
            )

        all_cases: list[dict[str, Any]] = []
        for asset in assets:
            if asset.parsed_cases_json:
                all_cases.extend(asset.parsed_cases_json)

        system_cases_query = (
            sync_db.query(TestCase)
            .filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
            )
            .all()
        )
        system_cases: list[dict[str, Any]] = []
        for sc in system_cases_query:
            system_cases.append({
                "case_id": sc.id,
                "title": sc.title,
                "module": sc.module,
                "precondition": sc.precondition,
                "steps": sc.steps_json or [],
                "expected_result": sc.expected_result,
                "priority": sc.priority,
            })

        requirement_keywords: list[str] = []
        if req_file_ids:
            from app.models.project import ProjectFile
            req_files = sync_db.query(ProjectFile).filter(
                ProjectFile.id.in_(req_file_ids),
                ProjectFile.project_id == project_id,
            ).all()
            for rf in req_files:
                if rf.original_filename:
                    name = os.path.splitext(rf.original_filename)[0]
                    requirement_keywords.extend(name.replace("_", " ").replace("-", " ").split())

        classification_items = _classify_history_cases(all_cases, system_cases, requirement_keywords)

        summary = HistoryClassificationSummary(
            reuse_count=sum(1 for i in classification_items if i.classification == "REUSE_CASE"),
            update_count=sum(1 for i in classification_items if i.classification == "UPDATE_CASE"),
            new_count=sum(1 for i in classification_items if i.classification == "NEW_CASE"),
            deprecated_count=sum(1 for i in classification_items if i.classification == "DEPRECATED_CASE"),
            confirm_required_count=sum(1 for i in classification_items if i.classification == "CONFIRM_REQUIRED"),
            total=len(classification_items),
        )

        result = HistoryClassificationResponse(summary=summary, items=classification_items)
        return result.model_dump()

    result_data = await db.run_sync(_align)
    return create_response(data=result_data)


@router.post("/import-system-cases")
async def import_system_cases(
    project_id: int = Form(...),
    case_ids: str = Form(...),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    import json

    try:
        parsed_case_ids = json.loads(case_ids)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"case_ids JSON 解析失败: {e}",
        ) from e

    def _import(sync_db: Session) -> HistoryAsset:
        _validate_project_permission(project_id, current_user.id, sync_db)

        cases = (
            sync_db.query(TestCase)
            .filter(
                TestCase.id.in_(parsed_case_ids),
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
            )
            .all()
        )
        if len(cases) != len(parsed_case_ids):
            found_ids = {c.id for c in cases}
            missing = set(parsed_case_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"以下用例不存在或不属于当前项目: {sorted(missing)}",
            )

        parsed_cases: list[dict[str, Any]] = []
        for case in cases:
            parsed_cases.append({
                "case_id": case.id,
                "case_no": case.case_no,
                "title": case.title,
                "module": case.module,
                "precondition": case.precondition,
                "steps": case.steps_json or [],
                "expected_result": case.expected_result,
                "priority": case.priority,
                "case_type": case.case_type,
            })

        asset = HistoryAsset(
            project_id=project_id,
            user_id=current_user.id,
            asset_type="system_cases",
            file_path=None,
            original_filename=None,
            parse_status="completed",
            parsed_cases_json=parsed_cases,
            case_count=len(parsed_cases),
        )
        sync_db.add(asset)
        sync_db.commit()
        sync_db.refresh(asset)
        return asset

    asset = await db.run_sync(_import)

    return create_response(data=_asset_to_upload_response(asset))


@router.get("/{asset_id}")
async def get_history_asset(
    asset_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get(sync_db: Session) -> HistoryAsset:
        asset = sync_db.query(HistoryAsset).filter(HistoryAsset.id == asset_id).first()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="历史资产不存在"
            )
        if asset.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此历史资产"
            )
        return asset

    asset = await db.run_sync(_get)
    return create_response(data=_asset_to_detail_response(asset))
