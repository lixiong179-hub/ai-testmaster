from pydantic import BaseModel, Field
from typing import Any, Literal
from datetime import datetime


class HistoryAssetUploadResponse(BaseModel):
    id: int
    project_id: int
    asset_type: str
    original_filename: str | None
    parse_status: str
    case_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryAssetDetailResponse(BaseModel):
    id: int
    project_id: int
    asset_type: str
    original_filename: str | None
    parse_status: str
    parse_error: str | None
    parsed_cases: list[dict[str, Any]]
    case_count: int
    batch_id: int | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class HistoryClassificationItem(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=80)
    classification: Literal["REUSE_CASE", "UPDATE_CASE", "NEW_CASE", "DEPRECATED_CASE", "CONFIRM_REQUIRED"]
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    history_case: dict[str, Any] | None = None
    suggested_case: dict[str, Any] | None = None
    diff_fields: dict[str, Any] | None = None
    reason: str = ""
    matched_system_case_id: int | None = None


class HistoryClassificationSummary(BaseModel):
    reuse_count: int = 0
    update_count: int = 0
    new_count: int = 0
    deprecated_count: int = 0
    confirm_required_count: int = 0
    total: int = 0


class HistoryClassificationResponse(BaseModel):
    summary: HistoryClassificationSummary
    items: list[HistoryClassificationItem]
