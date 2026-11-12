from pydantic import BaseModel, Field

from app.schemas.ui_prototype._enums import ParseStatusEnum, ReviewStatusEnum, UISourceEnum


class UIScreenBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    url: str | None = Field(None, max_length=2000)


class UIScreenCreate(UIScreenBase):
    project_id: int
    source: UISourceEnum = UISourceEnum.UPLOAD
    image_data: str | None = None


class UIScreenResponse(UIScreenBase):
    id: int
    project_id: int
    source: str
    image_url: str | None = None
    parse_status: str = ParseStatusEnum.PENDING.value
    review_status: str = ReviewStatusEnum.PENDING.value
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        from_attributes = True


class UIScreenDetailResponse(UIScreenResponse):
    elements_json: str | None = None
    raw_parse_result: str | None = None
    parse_error: str | None = None
    spec_for_case: str | None = None


class UIScreenParseRequest(BaseModel):
    screen_ids: list[int] | None = None
    prototype_project_id: int | None = None
    parse_mode: str | None = "text"
    force_reparse: bool = False
    extract_elements: bool = True
    generate_spec: bool = True


class UIScreenParseResponse(BaseModel):
    screen_id: int
    parse_status: str
    elements_count: int = 0
    spec_generated: bool = False
    error: str | None = None


class UIFlowGenerateRequest(BaseModel):
    project_id: int | None = None
    prototype_project_id: int | None = None
    screen_ids: list[int] | None = None
    flow_description: str | None = Field(None, max_length=1000)


class UIFlowGenerateResponse(BaseModel):
    project_id: int
    flow_data: str | None = None
    screen_count: int = 0
    error: str | None = None


class UISpecForCaseGeneration(BaseModel):
    screen_id: int
    title: str
    url: str | None = None
    elements_json: str | None = None
    spec_text: str | None = None


class UIScreenListResponse(BaseModel):
    items: list[UIScreenResponse]
    total: int
    page: int = 1
    page_size: int = 20


class UIScreenReviewRequest(BaseModel):
    review_status: ReviewStatusEnum
    review_comment: str | None = Field(None, max_length=500)


class UIPrototypeUploadRequest(BaseModel):
    project_id: int
    files: list[str] = Field(..., min_length=1)
