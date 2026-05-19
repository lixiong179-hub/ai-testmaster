from datetime import timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from loguru import logger

from app.models.review import IterationReview, ReviewDecision
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.services.lifecycle_service import transition as lifecycle_transition
from app.models.audit_log import AuditLog
from app.models.enums import ReviewStatus
from app.utils.db_time import utcnow
from app.services.review_service._errors import (
    REVIEW_UNDO_WINDOW_MINUTES,
    ReviewNotFinalizedError,
    ReviewUndoWindowExpiredError,
)


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

    _record_undo_metric(db, decision.target_id)

    return decision


def _reverse_lifecycle(db: Session, case_id: int) -> None:
    case: Optional[TestCase] = (
        db.query(TestCase).filter(TestCase.id == case_id, TestCase.is_deleted.is_(False)).first()
    )
    if case is None:
        return

    current_status = case.lifecycle_status
    if current_status == "archived":
        _restore_archived_case(db, case)
    elif current_status in ("deprecated", "needs_modify", "locator_broken", "pending_review"):
        try:
            lifecycle_transition(db, case_id=case.id, to_status="active")
        except Exception as e:
            logger.error("lifecycle reverse failed for case_id={}: {}", case_id, e)
    elif current_status == "draft":
        pass
    else:
        logger.debug("undo_decision: skipping lifecycle reversal for case_id={}, status={}", case_id, current_status)

    _deprecate_child_cases(db, case_id)


def _deprecate_child_cases(db: Session, parent_case_id: int) -> None:
    children = (
        db.query(TestCase).filter(TestCase.parent_case_id == parent_case_id, TestCase.is_deleted.is_(False)).all()
    )
    if not children:
        return

    for child in children:
        if child.lifecycle_status not in ("deprecated", "archived"):
            try:
                lifecycle_transition(
                    db, case_id=child.id, to_status="deprecated",
                    reason="parent_case_restored",
                )
            except Exception as e:
                logger.error("deprecate child case failed for case_id={}: {}", child.id, e)


def _restore_archived_case(db: Session, archived_case: TestCase) -> None:
    base_no = archived_case.case_no
    if "-v" in base_no:
        base_no = base_no.rsplit("-v", 1)[0]

    existing = (
        db.query(TestCase)
        .filter(TestCase.case_no.like(f"{base_no}-restored%"), TestCase.is_deleted.is_(False))
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
    enable_lifecycle_transition()
    try:
        db.add(restored)
        db.flush()
    finally:
        disable_lifecycle_transition()


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


def _record_undo_metric(db: Session, target_id: Optional[int]) -> None:
    try:
        from app.services.metrics_service import record_metric
        record_metric(
            "review_undo",
            detail={"target_id": target_id},
        )
    except Exception:
        logger.debug("记录评审撤销指标失败", exc_info=True)
