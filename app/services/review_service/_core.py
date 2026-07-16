from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReviewKind, ReviewStatus
from app.models.review import IterationReview, ReviewDecision, VALID_VERDICTS
from app.services.review_service._errors import (
    ReviewError,
    ReviewFinalizedError,
)
from app.utils.db_time import utcnow


def create_review(
    db: Session,
    iteration_id: int,
    kind: str,
) -> IterationReview:
    valid_kinds = {k.value for k in ReviewKind}
    if kind not in valid_kinds:
        raise ReviewError(f"Invalid review kind: {kind}")
    review = IterationReview(
        iteration_id=iteration_id,
        kind=kind,
        status=ReviewStatus.DRAFT.value,
    )
    db.add(review)
    db.flush()
    return review


def start_review(db: Session, review_id: int) -> Optional[IterationReview]:
    review = db.get(IterationReview, review_id)
    if review is None:
        return None
    if review.status != ReviewStatus.DRAFT.value:
        raise ReviewError(f"Review {review_id} is not in draft status")
    review.status = ReviewStatus.IN_PROGRESS.value
    db.flush()
    return review


def add_decision(
    db: Session,
    review_id: int,
    target_kind: str,
    target_id: int,
    ai_verdict: str,
    ai_confidence: int,
    ai_reason: Optional[str] = None,
    modification_hint: Optional[str] = None,
    deprecate_reason: Optional[str] = None,
    target_version: Optional[int] = None,
) -> ReviewDecision:
    review = db.get(IterationReview, review_id)
    if review is None:
        raise ReviewError(f"Review {review_id} not found")
    if review.is_finalized():
        raise ReviewFinalizedError(f"Review {review_id} is finalized, cannot add decision")

    from app.models.enums import ReviewTargetKind
    valid_target_kinds = {k.value for k in ReviewTargetKind}
    if target_kind not in valid_target_kinds:
        raise ReviewError(f"Invalid target_kind: {target_kind}")

    if ai_verdict not in VALID_VERDICTS:
        raise ReviewError(f"Invalid ai_verdict: {ai_verdict}, must be one of {VALID_VERDICTS}")

    if not (0 <= ai_confidence <= 100):
        raise ReviewError(f"Invalid ai_confidence: {ai_confidence}, must be 0-100")

    final_verdict, conflict = ReviewDecision.compute_final_verdict(ai_verdict, None)
    accepted_low_confidence = ai_confidence is not None and ai_confidence < 70

    decision = ReviewDecision(
        review_id=review_id,
        target_kind=target_kind,
        target_id=target_id,
        target_version=target_version,
        ai_verdict=ai_verdict,
        ai_confidence=ai_confidence,
        ai_reason=ai_reason,
        modification_hint=modification_hint,
        deprecate_reason=deprecate_reason,
        final_verdict=final_verdict,
        conflict_marker=conflict,
        accepted_low_confidence=accepted_low_confidence,
    )
    db.add(decision)
    db.flush()
    return decision


def set_human_verdict(
    db: Session,
    decision_id: int,
    human_verdict: str,
    human_user_id: int,
    human_reason: Optional[str] = None,
) -> Optional[ReviewDecision]:
    decision = db.get(ReviewDecision, decision_id)
    if decision is None:
        return None

    review = db.get(IterationReview, decision.review_id)
    if review is not None and review.is_finalized():
        raise ReviewFinalizedError(
            f"Cannot modify decision {decision_id}: review is finalized"
        )

    if human_verdict not in VALID_VERDICTS:
        raise ReviewError(f"Invalid human_verdict: {human_verdict}, must be one of {VALID_VERDICTS}")

    decision.human_verdict = human_verdict
    decision.human_user_id = human_user_id
    decision.human_reason = human_reason
    decision.decided_at = utcnow()

    final_verdict, conflict = ReviewDecision.compute_final_verdict(
        decision.ai_verdict, human_verdict,
    )
    decision.final_verdict = final_verdict
    decision.conflict_marker = conflict
    decision.accepted_low_confidence = False

    db.flush()
    return decision


def rollback_decision(
    db: Session,
    decision_id: int,
    user_id: int,
) -> Optional[ReviewDecision]:
    decision = db.get(ReviewDecision, decision_id)
    if decision is None:
        return None

    review = db.get(IterationReview, decision.review_id)
    if review is not None and review.is_finalized():
        from app.services.review_service._errors import ReviewDecisionImmutableError
        raise ReviewDecisionImmutableError(
            f"Cannot rollback decision {decision_id}: review is finalized"
        )

    old_human_verdict = decision.human_verdict
    decision.human_verdict = None
    decision.human_user_id = None
    decision.human_reason = None
    decision.final_verdict = decision.ai_verdict or "keep"
    decision.conflict_marker = False
    decision.accepted_low_confidence = (
        decision.ai_confidence is not None and decision.ai_confidence < 70
    )
    decision.decided_at = utcnow()

    from app.models.audit_log import AuditLog
    audit = AuditLog(
        action="review_rollback",
        target_kind="review_decision",
        target_id=decision.id,
        actor_id=user_id,
        detail={"old_human_verdict": old_human_verdict, "new_human_verdict": None},
    )
    db.add(audit)
    db.flush()
    return decision


def finalize_review(
    db: Session,
    review_id: int,
    finalized_by: int,
) -> Optional[IterationReview]:
    review = db.get(IterationReview, review_id)
    if review is None:
        return None
    if review.status != ReviewStatus.IN_PROGRESS.value:
        raise ReviewError(f"Review {review_id} is not_in_progress, cannot finalize")

    review.status = ReviewStatus.FINALIZED.value
    review.finalized_at = utcnow()
    review.finalized_by = finalized_by

    for lock in review.locks:
        db.delete(lock)

    db.flush()
    db.expire(review, ["locks"])

    try:
        from app.services.decision_application_service import apply_decisions
        apply_decisions(review_id=review.id, db=db)
    except Exception as e:
        from loguru import logger
        logger.error("apply_decisions failed for review_id={}: {}", review.id, e)
        review.status = ReviewStatus.IN_PROGRESS.value
        review.finalized_at = None
        review.finalized_by = None
        db.flush()
        raise

    return review


def cancel_review(
    db: Session,
    review_id: int,
) -> Optional[IterationReview]:
    review = db.get(IterationReview, review_id)
    if review is None:
        return None
    if review.is_finalized():
        raise ReviewFinalizedError(f"Review {review_id} is finalized, cannot cancel")

    review.status = ReviewStatus.CANCELLED.value
    for lock in review.locks:
        db.delete(lock)
    db.flush()
    db.expire(review, ["locks"])
    return review


# =============================================================
# 异步版本 - 供 async service / endpoint 使用
# 使用 AsyncSession + await db.execute/flush/commit
# finalize_review_async 中 apply_decisions 仍为同步实现，
# 通过 db.run_sync 桥接，避免阻塞事件循环
# =============================================================


async def create_review_async(
    db: AsyncSession,
    iteration_id: int,
    kind: str,
) -> IterationReview:
    """create_review 的异步版本。创建评审记录并 flush（不 commit，由调用方控制事务）。"""
    valid_kinds = {k.value for k in ReviewKind}
    if kind not in valid_kinds:
        raise ReviewError(f"Invalid review kind: {kind}")
    review = IterationReview(
        iteration_id=iteration_id,
        kind=kind,
        status=ReviewStatus.DRAFT.value,
    )
    db.add(review)
    await db.flush()
    return review


async def start_review_async(
    db: AsyncSession,
    review_id: int,
) -> Optional[IterationReview]:
    """start_review 的异步版本。将评审状态从 DRAFT 切换到 IN_PROGRESS。"""
    review = await db.get(IterationReview, review_id)
    if review is None:
        return None
    if review.status != ReviewStatus.DRAFT.value:
        raise ReviewError(f"Review {review_id} is not in draft status")
    review.status = ReviewStatus.IN_PROGRESS.value
    await db.flush()
    return review


async def add_decision_async(
    db: AsyncSession,
    review_id: int,
    target_kind: str,
    target_id: int,
    ai_verdict: str,
    ai_confidence: int,
    ai_reason: Optional[str] = None,
    modification_hint: Optional[str] = None,
    deprecate_reason: Optional[str] = None,
    target_version: Optional[int] = None,
) -> ReviewDecision:
    """add_decision 的异步版本。向评审添加 AI 决策并 flush。"""
    review = await db.get(IterationReview, review_id)
    if review is None:
        raise ReviewError(f"Review {review_id} not found")
    if review.is_finalized():
        raise ReviewFinalizedError(f"Review {review_id} is finalized, cannot add decision")

    from app.models.enums import ReviewTargetKind
    valid_target_kinds = {k.value for k in ReviewTargetKind}
    if target_kind not in valid_target_kinds:
        raise ReviewError(f"Invalid target_kind: {target_kind}")

    if ai_verdict not in VALID_VERDICTS:
        raise ReviewError(f"Invalid ai_verdict: {ai_verdict}, must be one of {VALID_VERDICTS}")

    if not (0 <= ai_confidence <= 100):
        raise ReviewError(f"Invalid ai_confidence: {ai_confidence}, must be 0-100")

    final_verdict, conflict = ReviewDecision.compute_final_verdict(ai_verdict, None)
    accepted_low_confidence = ai_confidence is not None and ai_confidence < 70

    decision = ReviewDecision(
        review_id=review_id,
        target_kind=target_kind,
        target_id=target_id,
        target_version=target_version,
        ai_verdict=ai_verdict,
        ai_confidence=ai_confidence,
        ai_reason=ai_reason,
        modification_hint=modification_hint,
        deprecate_reason=deprecate_reason,
        final_verdict=final_verdict,
        conflict_marker=conflict,
        accepted_low_confidence=accepted_low_confidence,
    )
    db.add(decision)
    await db.flush()
    return decision


async def finalize_review_async(
    db: AsyncSession,
    review_id: int,
    finalized_by: int,
) -> Optional[IterationReview]:
    """finalize_review 的异步版本。

    终结评审并应用决策。apply_decisions 内部有深层同步依赖
    （lifecycle_transition 等），通过 db.run_sync 桥接避免阻塞事件循环。
    """
    review = await db.get(IterationReview, review_id)
    if review is None:
        return None
    if review.status != ReviewStatus.IN_PROGRESS.value:
        raise ReviewError(f"Review {review_id} is not_in_progress, cannot finalize")

    review.status = ReviewStatus.FINALIZED.value
    review.finalized_at = utcnow()
    review.finalized_by = finalized_by

    for lock in review.locks:
        await db.delete(lock)

    await db.flush()
    db.expire(review, ["locks"])

    def _apply_decisions_sync(sync_db: Session) -> None:
        from app.services.decision_application_service import apply_decisions
        apply_decisions(review_id=review.id, db=sync_db)

    try:
        await db.run_sync(_apply_decisions_sync)
    except Exception as e:
        from loguru import logger
        logger.error("apply_decisions failed for review_id={}: {}", review.id, e)
        review.status = ReviewStatus.IN_PROGRESS.value
        review.finalized_at = None
        review.finalized_by = None
        await db.flush()
        raise

    return review
