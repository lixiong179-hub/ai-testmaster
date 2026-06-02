"""质量规则配置 Schema。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QualityRuleConfigUpdate(BaseModel):
    """更新质量规则配置请求体。"""
    rule_key: str = Field(..., min_length=1, max_length=80, description="规则键名")
    rule_value: Any = Field(..., description="规则值（JSON格式）")


class QualityRuleConfigResponse(BaseModel):
    """质量规则配置响应体。"""
    id: int
    project_id: int
    rule_key: str
    rule_value: Any
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
