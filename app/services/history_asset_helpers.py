"""历史资产端点共享工具（从 endpoints/_history_asset_helpers.py 下沉）。

仅包含 ORM → 响应转换，保持原 `_` 前缀函数名以兼容既有调用点。

注（2026-11-11，O-4b 收口）：
    原 `_validate_project_permission(project_id, user_id, db)` 已删除。它是
    R0-3 归属校验归一后的**残留死代码**（全仓 0 调用点），且错误码为
    404「项目不存在或无权限」，与 `access_deps.verify_project_access` 的
    403「无权限操作此项目」语义冲突，容易在排查时误导。
    项目归属校验请统一使用 `app.api.v1.endpoints.access_deps`。
"""
from app.models.history_asset import HistoryAsset
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
