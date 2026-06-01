from pydantic import BaseModel, Field
from typing import Any, Literal
from datetime import datetime

from app.schemas.test_case._core import TestCaseStep


class GenerationBatchCreate(BaseModel):
    project_id: int = Field(..., gt=0)
    entry_type: Literal["NEW_FEATURE_GENERATION"] = "NEW_FEATURE_GENERATION"
    scenario_type: Literal[
        "B1_REQUIREMENT_TESTPOINT",
        "A1_REQUIREMENT_TESTPOINT_UI",
    ]
    generation_strategy: Literal[
        "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        "FULL_CONTEXT_GENERATION_LITE",
    ]
    requirement_file_ids: list[int] = Field(default_factory=list, max_length=200)
    test_point_ids: list[int] = Field(default_factory=list, max_length=200)
    ui_screen_ids: list[int] = Field(default_factory=list, max_length=200)
    client_request_id: str | None = Field(None, max_length=80)


class GenerationBatchUpdate(BaseModel):
    status: Literal[
        "created",
        "context_ready",
        "generating",
        "preview_ready",
        "saving",
        "saved",
        "partial_saved",
        "failed",
    ] | None = None
    context_stats: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] | None = None
    evidence_refs: dict[str, Any] | None = None
    quality_summary: dict[str, Any] | None = None


class GenerationBatchResponse(BaseModel):
    id: int
    batch_no: str
    project_id: int
    user_id: int
    entry_type: str
    scenario_type: str
    generation_strategy: str
    status: str
    requirement_file_ids: list[int]
    test_point_ids: list[int]
    ui_screen_ids: list[int]
    context_stats: dict[str, Any]
    warnings: list[dict[str, Any]]
    evidence_refs: dict[str, Any]
    quality_summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class PreviewCasePayload(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=80)
    source_test_point_id: int | None = None
    requirement_file_id: int | None = None
    title: str = Field(..., min_length=1, max_length=255)
    module: str = Field("", max_length=100)
    precondition: str = ""
    steps: list[TestCaseStep] = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)
    priority: int = Field(2, ge=1, le=3)
    case_type: str = Field("manual", max_length=20)
    case_category: str | None = None
    quality_status: Literal["passed", "warning", "pending_review", "rejected"] = "pending_review"
    quality_issues: list[dict[str, Any]] = Field(default_factory=list)
    selected_for_save: bool = True
    source_refs: dict[str, Any] = Field(default_factory=dict)


class GenerationBatchSaveRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=100)
    save_mode: Literal["draft", "formal", "passed_only"]
    cases: list[PreviewCasePayload] = Field(..., min_length=1, max_length=500)


class BatchSaveFailureItem(BaseModel):
    client_id: str | None = None
    title: str | None = None
    reason: str


class GenerationBatchSaveResponse(BaseModel):
    batch_id: int
    idempotency_key: str
    save_mode: str
    saved_count: int
    failed_count: int
    saved_case_ids: list[int]
    failures: list[BatchSaveFailureItem]
    status: Literal["saved", "partial_saved", "failed"]
