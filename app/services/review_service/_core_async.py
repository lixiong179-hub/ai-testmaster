"""review_service 异步版本核心函数。

从 _core.py 拆出，与 sync 版本一一对应，供 async service / endpoint 使用。
使用 AsyncSession + await db.execute/flush/commit。
finalize_review_async 中 apply_decisions 仍为同步实现，
通过 db.run_sync 桥接，避免阻塞事件循环。
"""
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReviewKind, ReviewStatus, ReviewTargetKind
from app.models.review import IterationReview, ReviewDecision, VALID_VERDICTS
from app.services.review_service._errors import (
    ReviewError,
    ReviewFinalizedError,
)
from app.utils.db_time import utcnow


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


__all__ = [
    "create_review_async",
    "start_review_async",
    "add_decision_async",
    "finalize_review_async",
]
