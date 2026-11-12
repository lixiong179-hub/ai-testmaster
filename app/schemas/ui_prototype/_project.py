from pydantic import BaseModel, Field

from app.schemas.ui_prototype._enums import UISourceEnum


class UIPrototypeProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class UIPrototypeProjectCreate(UIPrototypeProjectBase):
    source: UISourceEnum = UISourceEnum.UPLOAD


class UIPrototypeProjectResponse(UIPrototypeProjectBase):
    id: int
    source: str
    screen_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        from_attributes = True
