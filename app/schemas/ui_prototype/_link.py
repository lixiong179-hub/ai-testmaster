from typing import Optional, Dict
from pydantic import BaseModel, Field

from app.schemas.ui_prototype._enums import UILinkAuthType


class UILinkBase(BaseModel):
    source_screen_id: int
    target_screen_id: int
    label: Optional[str] = Field(None, max_length=100)
    action_type: Optional[str] = Field(None, max_length=50)


class UILinkCreate(UILinkBase):
    auth_type: UILinkAuthType = UILinkAuthType.NONE
    auth_config: Optional[Dict] = None


class UILinkUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=100)
    action_type: Optional[str] = Field(None, max_length=50)
    auth_type: Optional[UILinkAuthType] = None
    auth_config: Optional[Dict] = None


class UILinkResponse(UILinkBase):
    id: int
    project_id: int
    auth_type: str = UILinkAuthType.NONE.value
    auth_config: Optional[Dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class UIFetchRequest(BaseModel):
    url: str = Field(..., max_length=2000)
    auth_type: UILinkAuthType = UILinkAuthType.NONE
    auth_config: Optional[Dict] = None
    wait_seconds: int = Field(5, ge=1, le=60)


class UIFetchResponse(BaseModel):
    screen_id: int
    image_url: Optional[str] = None
    fetch_status: str = "pending"
    error: Optional[str] = None
