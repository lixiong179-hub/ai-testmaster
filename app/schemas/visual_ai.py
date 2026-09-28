"""Visual AI Pydantic 模型定义。

定义 Visual AI API 端点的请求/响应 Schema，使用项目统一的 ApiResponse[T] 包装。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── 基线相关 Schema ──


class BaselineCreateRequest(BaseModel):
    """创建基线请求。"""

    name: str = Field(..., max_length=256, description="基线名称")
    page_url: str = Field(..., max_length=1024, description="被测页面URL")
    viewport_width: int = Field(..., gt=0, description="视口宽度")
    viewport_height: int = Field(..., gt=0, description="视口高度")
    match_level: str = Field("strict", description="对比模式: strict/layout/ignore_colors")
    test_case_id: Optional[int] = Field(None, description="关联测试用例ID")
    image_base64: str = Field(..., description="基线截图（base64编码）")
    dom_snapshot_base64: Optional[str] = Field(None, description="DOM快照（base64编码）")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "登录页-桌面端-1280x800",
                "page_url": "http://localhost:8080/login",
                "viewport_width": 1280,
                "viewport_height": 800,
                "match_level": "strict",
                "image_base64": "iVBORw0KGgo...",
            }
        }


class BaselineResponse(BaseModel):
    """基线响应。"""

    id: int
    project_id: int
    test_case_id: Optional[int] = None
    name: str
    page_url: str
    viewport_width: int
    viewport_height: int
    image_key: str
    image_width: int
    image_height: int
    match_level: str
    dom_snapshot_key: Optional[str] = None
    status: str
    version: int
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class BaselineUpdateRequest(BaseModel):
    """更新基线请求。"""

    image_base64: str = Field(..., description="新基线截图（base64编码）")
    match_level: Optional[str] = Field(None, description="新对比模式（可空，默认沿用原基线）")
    dom_snapshot_base64: Optional[str] = Field(None, description="新DOM快照（base64编码）")


class BaselineListResponse(BaseModel):
    """基线列表响应。"""

    total: int
    items: List[BaselineResponse]


# ── 对比相关 Schema ──


class CompareRequest(BaseModel):
    """视觉对比请求。"""

    page_url: str = Field(..., description="被测页面URL")
    viewport_width: int = Field(..., gt=0, description="视口宽度")
    viewport_height: int = Field(..., gt=0, description="视口高度")
    match_level: str = Field("strict", description="对比模式")
    current_image_base64: str = Field(..., description="当前截图（base64编码）")
    enable_llm_analysis: bool = Field(True, description="是否启用LLM语义分析")
    test_case_id: Optional[int] = Field(None, description="关联测试用例ID")
    test_result_id: Optional[int] = Field(None, description="关联测试结果ID")


class DiffResponse(BaseModel):
    """差异对比响应。"""

    diff_id: Optional[int] = None
    baseline_id: int
    diff_percentage: float
    diff_pixel_count: int
    total_pixel_count: int
    match_level: str
    status: str = "pending"
    llm_analysis: Optional[Dict[str, Any]] = None
    llm_token_cost: int = 0
    diff_image_base64: Optional[str] = None
    diff_report: Optional[str] = None

    class Config:
        from_attributes = True


# ── 审批相关 Schema ──


class ApprovalRequest(BaseModel):
    """审批请求。"""

    action: str = Field(..., description="审批动作: approve/reject/update_baseline")
    comment: Optional[str] = Field(None, description="审批意见")


class ApprovalResponse(BaseModel):
    """审批响应。"""

    id: int
    project_id: int
    diff_id: int
    baseline_id: int
    action: str
    comment: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewed_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class DiffListResponse(BaseModel):
    """差异列表响应。"""

    total: int
    items: List[DiffResponse]


__all__ = [
    "BaselineCreateRequest",
    "BaselineResponse",
    "BaselineUpdateRequest",
    "BaselineListResponse",
    "CompareRequest",
    "DiffResponse",
    "ApprovalRequest",
    "ApprovalResponse",
    "DiffListResponse",
]
