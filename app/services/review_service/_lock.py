from typing import List, Optional

from sqlalchemy import func
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
    verdict: Optional[str] = None,
    sort_by: Optional[str] = None,
    order: Optional[str] = "desc",
) -> List["ReviewDecision"]:
    """获取评审决策列表。

    P2-3: 将原在端点层 Python 内存中执行的 verdict 过滤与排序下推至 SQL，
    避免全量加载到内存后再过滤/排序。verdict/sort_by/order 参数语义保持兼容。
    """
    from app.models.review import ReviewDecision
    query = db.query(ReviewDecision).filter(
        ReviewDecision.review_id == review_id,
    )
    if target_kind:
        query = query.filter(ReviewDecision.target_kind == target_kind)
    if verdict is not None:
        query = query.filter(ReviewDecision.final_verdict == verdict)

    # 排序下推 SQL（原为 Python sorted()）
    if sort_by == "confidence":
        # 原 Python 实现: ai_confidence 为 None 时按 0 处理，使用 coalesce 保持一致
        order_col = func.coalesce(ReviewDecision.ai_confidence, 0)
    elif sort_by == "decided_at":
        order_col = ReviewDecision.decided_at
    else:
        order_col = None

    if order_col is not None:
        query = query.order_by(
            order_col.asc() if order == "asc" else order_col.desc()
        )
        # populate_existing: 强制从数据库重新加载，避免 identity map 缓存
        # 返回先前无序查询的结果顺序（POST /decide 端点先调用 get_decisions 无排序）
        query = query.populate_existing()

    return query.all()
