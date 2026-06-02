"""Prompt 模板版本管理 Schema - 请求与响应模型"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field


class PromptTemplateCreate(BaseModel):
    """注册新 Prompt 版本请求"""
    prompt_key: str = Field(..., min_length=1, max_length=80, description="Prompt唯一标识键")
    content: str = Field(..., min_length=1, description="Prompt内容")
    description: Optional[str] = Field(None, max_length=500, description="版本描述")


class PromptTemplateResponse(BaseModel):
    """Prompt 模板版本响应"""
    id: int
    prompt_key: str
    prompt_version: int
    prompt_hash: str
    content: str
    enabled: bool
    is_default: bool
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptTemplateListResponse(BaseModel):
    """Prompt 模板版本列表响应"""
    items: List[PromptTemplateResponse]
    total: int


class SetDefaultRequest(BaseModel):
    """设为默认版本请求"""
    version: int = Field(..., gt=0, description="要设为默认的版本号")


class RollbackRequest(BaseModel):
    """回滚请求"""
    target_version: int = Field(..., gt=0, description="回滚目标版本号")
