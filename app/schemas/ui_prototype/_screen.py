from typing import Optional, List
from pydantic import BaseModel, Field

from app.schemas.ui_prototype._enums import ParseStatusEnum, ReviewStatusEnum, UISourceEnum


class UIScreenBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=2000)


class UIScreenCreate(UIScreenBase):
    project_id: int
    source: UISourceEnum = UISourceEnum.UPLOAD
    image_data: Optional[str] = None


class UIScreenResponse(UIScreenBase):
    id: int
    project_id: int
    source: str
    image_url: Optional[str] = None
    parse_status: str = ParseStatusEnum.PENDING.value
    review_status: str = ReviewStatusEnum.PENDING.value
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class UIScreenDetailResponse(UIScreenResponse):
    elements_json: Optional[str] = None
    raw_parse_result: Optional[str] = None
    parse_error: Optional[str] = None
    spec_for_case: Optional[str] = None


class UIScreenParseRequest(BaseModel):
    screen_ids: Optional[List[int]] = None
    prototype_project_id: Optional[int] = None
    parse_mode: Optional[str] = "text"
    force_reparse: bool = False
    extract_elements: bool = True
    generate_spec: bool = True


class UIScreenParseResponse(BaseModel):
    screen_id: int
    parse_status: str
    elements_count: int = 0
    spec_generated: bool = False
    error: Optional[str] = None


class UIFlowGenerateRequest(BaseModel):
    project_id: Optional[int] = None
    prototype_project_id: Optional[int] = None
    screen_ids: Optional[List[int]] = None
    flow_description: Optional[str] = Field(None, max_length=1000)


class UIFlowGenerateResponse(BaseModel):
    project_id: int
    flow_data: Optional[str] = None
    screen_count: int = 0
    error: Optional[str] = None


class UISpecForCaseGeneration(BaseModel):
    screen_id: int
    title: str
    url: Optional[str] = None
    elements_json: Optional[str] = None
    spec_text: Optional[str] = None


class UIScreenListResponse(BaseModel):
    items: List[UIScreenResponse]
    total: int
    page: int = 1
    page_size: int = 20


class UIScreenReviewRequest(BaseModel):
    review_status: ReviewStatusEnum
    review_comment: Optional[str] = Field(None, max_length=500)


class UIPrototypeUploadRequest(BaseModel):
    project_id: int
    files: List[str] = Field(..., min_length=1)
