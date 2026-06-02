"""
运行时特性开关 Schema - FeatureFlag 的请求与响应模型
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class FeatureFlagCreate(BaseModel):
    """创建特性开关请求"""
    key: str = Field(..., min_length=1, max_length=80, description="特性开关唯一标识")
    name: str = Field(..., min_length=1, max_length=200, description="特性开关显示名称")
    description: Optional[str] = Field(None, max_length=500, description="特性开关描述")
    enabled: bool = Field(True, description="是否启用")
    rollout_percentage: int = Field(100, ge=0, le=100, description="灰度比例(0-100)")
    target_type: str = Field("all", pattern=r"^(all|specific)$", description="投放类型: all/specific")
    target_project_ids: Optional[List[int]] = Field(None, description="目标项目ID列表")


class FeatureFlagUpdate(BaseModel):
    """更新特性开关请求（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="特性开关显示名称")
    description: Optional[str] = Field(None, max_length=500, description="特性开关描述")
    enabled: Optional[bool] = Field(None, description="是否启用")
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100, description="灰度比例(0-100)")
    target_type: Optional[str] = Field(None, pattern=r"^(all|specific)$", description="投放类型: all/specific")
    target_project_ids: Optional[List[int]] = Field(None, description="目标项目ID列表")


class FeatureFlagResponse(BaseModel):
    """特性开关响应"""
    key: str
    name: str
    description: Optional[str] = None
    enabled: bool
    rollout_percentage: int
    target_project_ids: Optional[List[int]] = None
    target_type: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
