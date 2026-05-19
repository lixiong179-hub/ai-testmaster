from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.review import IterationReview, ReviewLock
from app.services.review_service._errors import (
    ReviewError,
    ReviewFinalizedError,
    ReviewLockConflictError,
)
from app.utils.db_time import utcnow


def acquire_lock(
    db: Session,
    review_id: int,
    target_kind: str,
    target_id: int,
) -> ReviewLock:
    review = db.get(IterationReview, review_id)
    if review is None:
        raise ReviewError(f"Review {review_id} not found")
    if review.is_finalized():
        raise ReviewFinalizedError(f"Review {review_id} is finalized, cannot acquire lock")

    now = utcnow()
    existing = (
        db.query(ReviewLock)
        .filter(
            ReviewLock.target_kind == target_kind,
            ReviewLock.target_id == target_id,
            ReviewLock.expires_at > now,
        )
        .first()
    )
    if existing is not None:
        raise ReviewLockConflictError(
            f"Target ({target_kind}, {target_id}) is already locked until {existing.expires_at}"
        )

    lock = ReviewLock(
        review_id=review_id,
        target_kind=target_kind,
        target_id=target_id,
        expires_at=ReviewLock.default_expiry(),
    )
    db.add(lock)
    db.flush()
    return lock


def release_lock(db: Session, lock_id: int) -> bool:
    lock = db.get(ReviewLock, lock_id)
    if lock is None:
        return False
    db.delete(lock)
    db.flush()
    return True


def cleanup_expired_locks(db: Session) -> int:
    now = utcnow()
    expired = db.query(ReviewLock).filter(ReviewLock.expires_at <= now).all()
    count = len(expired)
    for lock in expired:
        db.delete(lock)
    db.flush()
    return count


def get_review(db: Session, review_id: int) -> Optional[IterationReview]:
    return db.get(IterationReview, review_id)


def list_reviews(
    db: Session,
    iteration_id: int,
    status: Optional[str] = None,
) -> List[IterationReview]:
    query = db.query(IterationReview).filter(
        IterationReview.iteration_id == iteration_id,
    )
    if status:
        query = query.filter(IterationReview.status == status)
    return query.order_by(IterationReview.created_at.desc()).all()


def get_decisions(
    db: Session,
    review_id: int,
    target_kind: Optional[str] = None,
) -> List["ReviewDecision"]:
    from app.models.review import ReviewDecision
    query = db.query(ReviewDecision).filter(
        ReviewDecision.review_id == review_id,
    )
    if target_kind:
        query = query.filter(ReviewDecision.target_kind == target_kind)
    return query.all()
