from pydantic import BaseModel, Field

from app.schemas.ui_prototype._enums import UILinkAuthType


class UILinkBase(BaseModel):
    source_screen_id: int
    target_screen_id: int
    label: str | None = Field(None, max_length=100)
    action_type: str | None = Field(None, max_length=50)


class UILinkCreate(UILinkBase):
    auth_type: UILinkAuthType = UILinkAuthType.NONE
    auth_config: dict | None = None


class UILinkUpdate(BaseModel):
    label: str | None = Field(None, max_length=100)
    action_type: str | None = Field(None, max_length=50)
    auth_type: UILinkAuthType | None = None
    auth_config: dict | None = None


class UILinkResponse(UILinkBase):
    id: int
    project_id: int
    auth_type: str = UILinkAuthType.NONE.value
    auth_config: dict | None = None
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        from_attributes = True


class UIFetchRequest(BaseModel):
    url: str = Field(..., max_length=2000)
    auth_type: UILinkAuthType = UILinkAuthType.NONE
    auth_config: dict | None = None
    wait_seconds: int = Field(5, ge=1, le=60)


class UIFetchResponse(BaseModel):
    screen_id: int
    image_url: str | None = None
    fetch_status: str = "pending"
    error: str | None = None
