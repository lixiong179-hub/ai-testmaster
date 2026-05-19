import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import TestCaseLifecycleStatus
from app.services.lifecycle_service._rules import (
    TRANSITION_RULES,
    _VALID_TRANSITIONS,
    IllegalStateTransition,
    MissingReviewError,
    CooldownNotElapsedError,
    MissingDeprecateReasonError,
)
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.utils.db_time import utcnow

logger = logging.getLogger(__name__)


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in _VALID_TRANSITIONS.get(from_status, set())


def transition(
    db: Session,
    case_id: int,
    to_status: str,
    *,
    review_id: Optional[int] = None,
    reason: Optional[str] = None,
    actor_id: Optional[int] = None,
    modification_hint: Optional[str] = None,
    auto_approve: bool = False,
) -> TestCase:
    test_case = db.query(TestCase).filter(TestCase.id == case_id, TestCase.is_deleted.is_(False)).first()
    if test_case is None:
        raise ValueError(f"TestCase id={case_id} not found")

    from_status = test_case.lifecycle_status

    if not can_transition(from_status, to_status):
        raise IllegalStateTransition(from_status, to_status)

    rule = TRANSITION_RULES[(from_status, to_status)]
    requires = rule.get("requires", [])

    if "review_id" in requires and review_id is None:
        raise MissingReviewError(f"{from_status} → {to_status}")

    if "deprecate_reason" in requires and not reason:
        raise MissingDeprecateReasonError(f"{from_status} → {to_status}")

    if (
        from_status == TestCaseLifecycleStatus.PENDING_REVIEW.value
        and to_status == TestCaseLifecycleStatus.ACTIVE.value
        and not auto_approve
    ):
        logger.info(
            "pending_review → active: manual approval, case_id=%d, actor_id=%s",
            case_id, actor_id,
        )

    if rule.get("cooldown_hours"):
        _check_cooldown(test_case)

    old_status = from_status
    try:
        enable_lifecycle_transition()
        test_case.lifecycle_status = to_status

        if review_id is not None:
            test_case.last_review_id = review_id

        if to_status == TestCaseLifecycleStatus.DEPRECATED.value:
            test_case.deprecated_at = utcnow()

        if rule.get("side_effect") == "archive_old_version":
            test_case.lifecycle_status = TestCaseLifecycleStatus.ARCHIVED.value
            _create_new_version_case(db, test_case, modification_hint, actor_id)

        db.flush()
    finally:
        disable_lifecycle_transition()

    _write_audit_log(
        db=db,
        case_id=case_id,
        old_status=old_status,
        new_status=test_case.lifecycle_status,
        review_id=review_id,
        reason=reason,
        actor_id=actor_id,
        modification_hint=modification_hint,
        auto_approve=auto_approve,
    )

    return test_case


def _check_cooldown(test_case: TestCase) -> None:
    from datetime import datetime, timedelta
    from app.core.config import settings

    deprecated_at = test_case.deprecated_at or test_case.update_time or test_case.create_time
    if deprecated_at is None:
        return

    if isinstance(deprecated_at, str):
        deprecated_at = datetime.fromisoformat(deprecated_at)

    cooldown_hours = settings.LIFECYCLE_DEPRECATE_COOLDOWN_HOURS
    now = utcnow()
    if deprecated_at.tzinfo is not None:
        deprecated_at = deprecated_at.replace(tzinfo=None)
    elapsed = now - deprecated_at
    required = timedelta(hours=cooldown_hours)

    if elapsed < required:
        remaining = required - elapsed
        remaining_hours = remaining.total_seconds() / 3600
        raise CooldownNotElapsedError(remaining_hours)


def _create_new_version_case(
    db: Session,
    old_case: TestCase,
    modification_hint: Optional[str],
    actor_id: Optional[int],
) -> None:
    _ = db.query(TestCase).filter(
        TestCase.parent_case_id == old_case.id,
        TestCase.is_deleted.is_(False),
    ).count()
    root_case_id = old_case.id
    root_case = old_case
    while root_case.parent_case_id is not None:
        parent = db.query(TestCase).filter(TestCase.id == root_case.parent_case_id, TestCase.is_deleted.is_(False)).first()
        if parent is None:
            break
        root_case = parent
        root_case_id = root_case.id
    total_versions = db.query(TestCase).filter(
        (TestCase.parent_case_id == root_case_id) | (TestCase.id == root_case_id),
        TestCase.is_deleted.is_(False)
    ).count()
    next_version = total_versions + 1

    base_no = root_case.case_no
    if "-v" in base_no:
        base_no = base_no.rsplit("-v", 1)[0]
    new_case_no = f"{base_no}-v{next_version}"

    new_case = TestCase(
        project_id=old_case.project_id,
        case_no=new_case_no,
        module=old_case.module,
        title=old_case.title,
        precondition=old_case.precondition,
        steps_json=old_case.steps_json,
        expected_result=old_case.expected_result,
        priority=old_case.priority,
        case_type=old_case.case_type,
        exec_script=old_case.exec_script,
        test_category=old_case.test_category,
        generate_status=old_case.generate_status,
        lifecycle_status=TestCaseLifecycleStatus.PENDING_REVIEW.value,
        test_point_id=old_case.test_point_id,
        summary=old_case.summary,
        summary_version=old_case.summary_version,
        summary_model_version=old_case.summary_model_version,
        parent_case_id=old_case.id,
    )
    db.add(new_case)
    db.flush()


def _write_audit_log(
    db: Session,
    case_id: int,
    old_status: str,
    new_status: str,
    review_id: Optional[int],
    reason: Optional[str],
    actor_id: Optional[int],
    modification_hint: Optional[str],
    auto_approve: bool,
) -> None:
    detail = {
        "from": old_status,
        "to": new_status,
        "auto_approve": auto_approve,
    }
    if review_id is not None:
        detail["review_id"] = review_id
    if reason is not None:
        detail["reason"] = reason
    if modification_hint is not None:
        detail["modification_hint"] = modification_hint

    try:
        from app.services.audit_service import log_action
        log_action(
            db=db,
            action="lifecycle_transition",
            actor_id=actor_id,
            target_kind="test_case",
            target_id=case_id,
            detail=detail,
        )
    except Exception as e:
        logger.error(
            "Failed to write audit log for lifecycle_transition: "
            "case_id=%d, %s → %s, error=%s",
            case_id, old_status, new_status, e,
        )
