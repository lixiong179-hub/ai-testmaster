"""评审服务 — IterationReview / ReviewDecision / ReviewLock 业务逻辑

核心规则:
    - review_decision 不可变：finalize 后禁止 update
    - review_lock 独占：同一 (target_kind, target_id) 在锁定期内不能同时被锁定
    - 锁过期自动失效（24h TTL）
    - finalize 前可回滚单条决策（human_verdict→NULL, final_verdict→ai_verdict）
    - finalize 后可撤销（undo）：1h 时间窗口 + audit_log + 生命周期逆操作
"""
from datetime import timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.enums import ReviewKind, ReviewStatus, ReviewTargetKind
from app.models.review import IterationReview, ReviewDecision, ReviewLock, VALID_VERDICTS
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.models.audit_log import AuditLog
from app.utils.db_time import utcnow
from loguru import logger

REVIEW_UNDO_WINDOW_MINUTES = 60


class ReviewError(Exception):
    pass


class ReviewFinalizedError(ReviewError):
    pass


class ReviewLockConflictError(ReviewError):
    pass


class ReviewDecisionImmutableError(ReviewError):
    pass


class ReviewUndoWindowExpiredError(ReviewError):
    pass


class ReviewNotFinalizedError(ReviewError):
    pass


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
        raise ReviewError(f"Review {review_id} is not in_progress, cannot finalize")

    review.status = ReviewStatus.FINALIZED.value
    review.finalized_at = utcnow()
    review.finalized_by = finalized_by

    for lock in review.locks:
        db.delete(lock)

    db.flush()
    db.expire(review, ["locks"])
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


def undo_decision(
    db: Session,
    decision_id: int,
    user_id: int,
) -> Optional[ReviewDecision]:
    decision = db.get(ReviewDecision, decision_id)
    if decision is None:
        return None

    review = db.get(IterationReview, decision.review_id)
    if review is None or not review.is_finalized():
        raise ReviewNotFinalizedError(
            f"Cannot undo decision {decision_id}: review not finalized"
        )

    if review.finalized_at is None:
        raise ReviewNotFinalizedError(
            f"Cannot undo decision {decision_id}: finalized_at is None"
        )

    elapsed = utcnow() - review.finalized_at
    elapsed_minutes = round(elapsed.total_seconds() / 60, 1)
    window = timedelta(minutes=REVIEW_UNDO_WINDOW_MINUTES)
    if elapsed >= window:
        raise ReviewUndoWindowExpiredError(
            f"Undo window expired: {elapsed_minutes}min > {REVIEW_UNDO_WINDOW_MINUTES}min"
        )

    old_final_verdict = decision.final_verdict
    old_human_verdict = decision.human_verdict

    if decision.target_kind == "case" and decision.target_id is not None:
        _reverse_lifecycle(db, decision.target_id)

    decision.human_verdict = None
    decision.human_user_id = None
    decision.human_reason = None
    decision.final_verdict = decision.ai_verdict or "keep"
    decision.conflict_marker = False
    decision.accepted_low_confidence = (
        decision.ai_confidence is not None and decision.ai_confidence < 70
    )
    decision.decided_at = utcnow()

    audit = AuditLog(
        action="review_undo",
        target_kind="review_decision",
        target_id=decision.id,
        actor_id=user_id,
        detail={
            "old_final_verdict": old_final_verdict,
            "old_human_verdict": old_human_verdict,
            "new_final_verdict": decision.final_verdict,
            "elapsed_minutes": elapsed_minutes,
            "target_case_id": decision.target_id,
        },
    )
    db.add(audit)
    db.flush()
    return decision


def _reverse_lifecycle(db: Session, case_id: int) -> None:
    case: Optional[TestCase] = (
        db.query(TestCase).filter(TestCase.id == case_id).first()
    )
    if case is None:
        return

    current_status = case.lifecycle_status
    try:
        enable_lifecycle_transition()

        if current_status == "archived":
            _restore_archived_case(db, case)
        elif current_status in ("deprecated", "needs_modify", "locator_broken", "pending_review"):
            case.lifecycle_status = "active"
        elif current_status == "draft":
            pass
        else:
            logger.debug("undo_decision: skipping lifecycle reversal for case_id={}, status={}", case_id, current_status)

        db.flush()
    finally:
        disable_lifecycle_transition()

    _deprecate_child_cases(db, case_id)


def _deprecate_child_cases(db: Session, parent_case_id: int) -> None:
    children = (
        db.query(TestCase).filter(TestCase.parent_case_id == parent_case_id).all()
    )
    if not children:
        return

    try:
        enable_lifecycle_transition()
        for child in children:
            if child.lifecycle_status not in ("deprecated", "archived"):
                child.lifecycle_status = "deprecated"
        db.flush()
    finally:
        disable_lifecycle_transition()


def _restore_archived_case(db: Session, archived_case: TestCase) -> None:
    base_no = archived_case.case_no
    if "-v" in base_no:
        base_no = base_no.rsplit("-v", 1)[0]

    existing = (
        db.query(TestCase)
        .filter(TestCase.case_no.like(f"{base_no}-restored%"))
        .count()
    )
    case_no = f"{base_no}-restored-{existing + 1}" if existing > 0 else f"{base_no}-restored"

    restored = TestCase(
        project_id=archived_case.project_id,
        case_no=case_no,
        module=archived_case.module,
        title=archived_case.title,
        precondition=archived_case.precondition,
        steps_json=archived_case.steps_json,
        expected_result=archived_case.expected_result,
        priority=archived_case.priority,
        case_type=archived_case.case_type,
        exec_script=archived_case.exec_script,
        test_category=archived_case.test_category,
        generate_status=archived_case.generate_status,
        lifecycle_status="draft",
        test_point_id=archived_case.test_point_id,
        summary=archived_case.summary,
        summary_version=archived_case.summary_version,
        summary_model_version=archived_case.summary_model_version,
    )
    db.add(restored)
    db.flush()


def undo_finalize(
    db: Session,
    review_id: int,
    user_id: int,
) -> Optional[IterationReview]:
    review = db.get(IterationReview, review_id)
    if review is None:
        return None

    if not review.is_finalized():
        raise ReviewNotFinalizedError(
            f"Review {review_id} is not finalized"
        )

    if review.finalized_at is None:
        raise ReviewNotFinalizedError(
            f"Review {review_id} has no finalized_at"
        )

    elapsed = utcnow() - review.finalized_at
    elapsed_minutes = round(elapsed.total_seconds() / 60, 1)
    window = timedelta(minutes=REVIEW_UNDO_WINDOW_MINUTES)
    if elapsed >= window:
        raise ReviewUndoWindowExpiredError(
            f"Undo window expired: {elapsed_minutes}min > {REVIEW_UNDO_WINDOW_MINUTES}min"
        )

    all_decisions = (
        db.query(ReviewDecision).filter(ReviewDecision.review_id == review_id).all()
    )

    rolled_back_count = 0
    for decision in all_decisions:
        try:
            savepoint = db.begin_nested()

            if decision.target_kind == "case" and decision.target_id is not None:
                _reverse_lifecycle(db, decision.target_id)

            decision.human_verdict = None
            decision.human_user_id = None
            decision.human_reason = None
            decision.final_verdict = decision.ai_verdict or "keep"
            decision.conflict_marker = False
            decision.accepted_low_confidence = (
                decision.ai_confidence is not None and decision.ai_confidence < 70
            )
            decision.decided_at = utcnow()

            savepoint.commit()
            rolled_back_count += 1
        except Exception:
            savepoint.rollback()
            logger.warning(
                "undo_finalize: failed to rollback decision_id={}, target_id={}",
                decision.id, decision.target_id,
            )

    review.status = ReviewStatus.IN_PROGRESS.value
    review.finalized_at = None
    review.finalized_by = None

    audit = AuditLog(
        action="review_undo",
        target_kind="iteration_review",
        target_id=review.id,
        actor_id=user_id,
        detail={
            "event": "undo_finalize",
            "elapsed_minutes": elapsed_minutes,
            "rolled_back_decisions": rolled_back_count,
        },
    )
    db.add(audit)
    db.flush()
    return review


def get_decisions(
    db: Session,
    review_id: int,
    target_kind: Optional[str] = None,
) -> List[ReviewDecision]:
    query = db.query(ReviewDecision).filter(
        ReviewDecision.review_id == review_id,
    )
    if target_kind:
        query = query.filter(ReviewDecision.target_kind == target_kind)
    return query.all()
