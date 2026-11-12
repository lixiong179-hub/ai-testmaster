"""评审 Inbox 请求/响应模型（从 _schemas.py 拆出，schema 属端点层保留）。"""

from pydantic import BaseModel, Field


class DecisionOut(BaseModel):
    id: int
    target_kind: str
    target_id: int
    target_version: int | None = None
    ai_verdict: str | None = None
    ai_confidence: int | None = None
    ai_reason: str | None = None
    modification_hint: str | None = None
    deprecate_reason: str | None = None
    human_verdict: str | None = None
    human_user_id: int | None = None
    human_reason: str | None = None
    final_verdict: str | None = None
    conflict_marker: bool = False
    accepted_low_confidence: bool = False
    decided_at: str | None = None

    model_config = {"from_attributes": True}


class DecideRequest(BaseModel):
    human_verdict: str = Field(..., description="人工判定: keep/modify/deprecate")
    human_reason: str | None = Field(None, description="判定理由")


class BatchDecideItem(BaseModel):
    decision_id: int
    human_verdict: str = Field(..., description="人工判定: keep/modify/deprecate")
    human_reason: str | None = Field(None)


class BatchDecideRequest(BaseModel):
    decisions: list[BatchDecideItem] = Field(..., min_length=1, max_length=500)


class RollbackRequest(BaseModel):
    reason: str | None = Field(None, description="回滚原因")


class FinalizeResponse(BaseModel):
    success: bool
    detail: str = ""
    undone_case_count: int = 0
    rolled_back_decision_ids: list[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}
