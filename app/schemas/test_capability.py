"""
业务能力 Schema - TestCapability 的请求与响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.models.enums import CAPABILITY_STATUS_PATTERN


class TestCapabilityBase(BaseModel):
    """能力基础字段"""
    key: str = Field(..., min_length=1, max_length=100, description="能力唯一标识，同项目内唯一")
    title: str = Field(..., min_length=1, max_length=255, description="能力显示名称")
    description: Optional[str] = Field(None, description="能力描述")
    status: str = Field("active", pattern=CAPABILITY_STATUS_PATTERN, description="能力状态")


class TestCapabilityCreate(TestCapabilityBase):
    """创建能力请求"""
    project_id: int = Field(..., description="项目ID")


class TestCapabilityUpdate(BaseModel):
    """更新能力请求"""
    key: Optional[str] = Field(None, min_length=1, max_length=100, description="能力唯一标识")
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="能力显示名称")
    description: Optional[str] = Field(None, description="能力描述")
    status: Optional[str] = Field(None, pattern=CAPABILITY_STATUS_PATTERN, description="能力状态")


class TestCapabilityResponse(TestCapabilityBase):
    """能力响应"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
