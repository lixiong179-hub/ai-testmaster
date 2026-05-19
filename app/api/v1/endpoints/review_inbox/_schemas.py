from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.review import IterationReview, ReviewDecision
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.services import review_service


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


def _verify_review_access(
    db: Session, review_id: int, current_user: User
) -> IterationReview:
    review = db.get(IterationReview, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="评审不存在")
    iteration = db.get(Iteration, review.iteration_id)
    if iteration is None:
        raise HTTPException(status_code=404, detail="迭代不存在")
    project = db.query(Project).filter(
        Project.id == iteration.project_id,
        Project.user_id == current_user.id,
    ).first()
    if project is None:
        raise HTTPException(status_code=403, detail="无权限操作此评审")
    return review


def _serialize_decision(d: ReviewDecision) -> dict:
    return {
        "id": d.id,
        "target_kind": d.target_kind,
        "target_id": d.target_id,
        "target_version": d.target_version,
        "ai_verdict": d.ai_verdict,
        "ai_confidence": d.ai_confidence,
        "ai_reason": d.ai_reason,
        "modification_hint": d.modification_hint,
        "deprecate_reason": d.deprecate_reason,
        "human_verdict": d.human_verdict,
        "human_user_id": d.human_user_id,
        "human_reason": d.human_reason,
        "final_verdict": d.final_verdict,
        "conflict_marker": d.conflict_marker,
        "accepted_low_confidence": d.accepted_low_confidence,
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
    }


def _check_zero_edit_confirmation(
    db: Session,
    decision: ReviewDecision,
    ai_verdict: Optional[str],
    human_verdict: str,
    human_reason: Optional[str],
) -> None:
    if ai_verdict == human_verdict and not human_reason:
        try:
            from app.services.metrics_service import record_metric
            from app.models.test_case import TestCase
            project_id = None
            if decision.target_kind == "case" and decision.target_id:
                case = db.query(TestCase).filter(
                    TestCase.id == decision.target_id,
                    TestCase.is_deleted.is_(False),
                ).first()
                if case:
                    project_id = case.project_id
            record_metric(
                "confirmed_zero_edit",
                project_id=project_id,
                detail={
                    "decision_id": decision.id,
                    "ai_verdict": ai_verdict,
                    "human_verdict": human_verdict,
                },
            )
        except Exception:
            logger.debug("记录confirmed_zero_edit指标失败", exc_info=True)


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return current_user
