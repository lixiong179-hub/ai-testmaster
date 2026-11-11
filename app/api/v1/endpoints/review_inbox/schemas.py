"""评审 Inbox 请求/响应模型（从 _schemas.py 拆出，schema 属端点层保留）。"""
from typing import List, Optional

from pydantic import BaseModel, Field


class DecisionOut(BaseModel):
    id: int
    target_kind: str
    target_id: int
    target_version: Optional[int] = None
    ai_verdict: Optional[str] = None
    ai_confidence: Optional[int] = None
    ai_reason: Optional[str] = None
    modification_hint: Optional[str] = None
    deprecate_reason: Optional[str] = None
    human_verdict: Optional[str] = None
    human_user_id: Optional[int] = None
    human_reason: Optional[str] = None
    final_verdict: Optional[str] = None
    conflict_marker: bool = False
    accepted_low_confidence: bool = False
    decided_at: Optional[str] = None

    model_config = {"from_attributes": True}


class DecideRequest(BaseModel):
    human_verdict: str = Field(..., description="人工判定: keep/modify/deprecate")
    human_reason: Optional[str] = Field(None, description="判定理由")


class BatchDecideItem(BaseModel):
    decision_id: int
    human_verdict: str = Field(..., description="人工判定: keep/modify/deprecate")
    human_reason: Optional[str] = Field(None)


class BatchDecideRequest(BaseModel):
    decisions: List[BatchDecideItem] = Field(..., min_length=1, max_length=500)


class RollbackRequest(BaseModel):
    reason: Optional[str] = Field(None, description="回滚原因")


class FinalizeResponse(BaseModel):
    success: bool
    detail: str = ""
    undone_case_count: int = 0
    rolled_back_decision_ids: List[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}
