"""评审 Inbox 端点共享工具（从 endpoints/review_inbox/_schemas.py 下沉）。

包含评审访问校验、决策序列化与「零编辑确认」指标记录，
schema 与 `require_admin` 依赖仍保留在端点层。
"""

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.models.iteration import Iteration
from app.models.project import Project
from app.models.review import IterationReview, ReviewDecision
from app.models.user import User


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
    ai_verdict: str | None,
    human_verdict: str,
    human_reason: str | None,
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
