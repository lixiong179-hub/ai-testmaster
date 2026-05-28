"""Pipeline 相关 Pydantic Schema

提供 Pipeline 产物详情查询的响应模型。
"""
from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class ArtifactDetailResponse(BaseModel):
    """产物详情响应模型。

    Attributes:
        id: 产物 ID
        run_id: 关联的 Pipeline 运行 ID
        kind: 产物类型
        schema_version: 产物 schema 版本
        payload: 产物 JSON 载荷（大 payload 可能被截断）
        confidence: 置信度分数
        provenance: 产物来源信息
        content_hash: 产物内容哈希
        created_at: 创建时间
        truncated: payload 是否被截断
        truncated_reason: 截断原因描述
    """
    id: int = Field(..., description="产物 ID")
    run_id: int = Field(..., description="关联的 Pipeline 运行 ID")
    kind: str = Field(..., description="产物类型")
    schema_version: str = Field(default="1.0", description="产物 schema 版本")
    payload: Optional[Any] = Field(default=None, description="产物 JSON 载荷")
    confidence: Optional[float] = Field(default=None, description="置信度分数")
    provenance: Optional[dict] = Field(default=None, description="产物来源信息")
    content_hash: str = Field(..., description="产物内容哈希")
    created_at: datetime = Field(..., description="创建时间")
    truncated: bool = Field(default=False, description="payload 是否被截断")
    truncated_reason: Optional[str] = Field(default=None, description="截断原因")

    class Config:
        from_attributes = True
