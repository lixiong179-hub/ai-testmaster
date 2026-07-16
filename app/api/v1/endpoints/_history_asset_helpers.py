from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.history_asset import HistoryAsset
from app.models.project import Project
from app.schemas.history_asset import (
    HistoryAssetDetailResponse,
    HistoryAssetUploadResponse,
)


def _asset_to_upload_response(asset: HistoryAsset) -> dict:
    return HistoryAssetUploadResponse(
        id=asset.id,
        project_id=asset.project_id,
        asset_type=asset.asset_type,
        original_filename=asset.original_filename,
        parse_status=asset.parse_status,
        case_count=asset.case_count,
        created_at=asset.created_at,
    ).model_dump()


def _asset_to_detail_response(asset: HistoryAsset) -> dict:
    return HistoryAssetDetailResponse(
        id=asset.id,
        project_id=asset.project_id,
        asset_type=asset.asset_type,
        original_filename=asset.original_filename,
        parse_status=asset.parse_status,
        parse_error=asset.parse_error,
        parsed_cases=asset.parsed_cases_json or [],
        case_count=asset.case_count,
        batch_id=asset.batch_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    ).model_dump()


def _validate_project_permission(project_id: int, user_id: int, db: Session) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限"
        )
    return project
