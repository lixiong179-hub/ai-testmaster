import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Optional, List

from loguru import logger
from sqlalchemy.orm import Session

from app.services.lifecycle_service import transition as lifecycle_transition
from app.services.lifecycle_service import (
    IllegalStateTransition,
    MissingReviewError,
    MissingDeprecateReasonError,
)
from app.pipelines.steps.reconciliation import MergedAction
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition


@dataclass
class ApplyDecision:
    target_kind: str
    target_id: Optional[int]
    merged_action: str
    modification_hint: Optional[str] = None
    deprecate_reason: Optional[str] = None
    confidence: float = 0.0
    review_id: Optional[int] = None
    case_data: Optional[dict] = field(default=None)


@dataclass
class ApplyResult:
    target_kind: str
    target_id: Optional[int]
    action: str
    success: bool
    new_case_id: Optional[int] = None
    error: Optional[str] = None
    deferred: bool = False
    deferred_reason: Optional[str] = None


def apply_decisions(
    db: Session,
    decisions: Optional[List[ApplyDecision]] = None,
    actor_id: Optional[int] = None,
    review_id: Optional[int] = None,
) -> List[ApplyResult]:
    if decisions is None and review_id is not None:
        from app.services.decision_application_service._handlers import _load_decisions_from_review
        decisions = _load_decisions_from_review(review_id, db)
    if decisions is None:
        decisions = []
    results: List[ApplyResult] = []
    for decision in decisions:
        result = apply_single(db, decision, actor_id=actor_id)
        results.append(result)
    return results


_ACTION_HANDLERS = {
    MergedAction.KEEP: lambda db, d, _a: _handle_keep(d),
    MergedAction.NEEDS_MODIFY: lambda db, d, a: _handle_needs_modify(db, d, a),
    MergedAction.LOCATOR_BROKEN: lambda db, d, a: _handle_locator_broken(db, d, a),
    MergedAction.LOCATOR_AND_MODIFY: lambda db, d, a: _handle_locator_and_modify(db, d, a),
    MergedAction.DEPRECATE: lambda db, d, a: _handle_deprecate(db, d, a),
    MergedAction.ADD_NEW: lambda db, d, a: _handle_add_new(db, d, a),
    MergedAction.CONFLICT: lambda db, d, _a: _handle_conflict(d),
    MergedAction.PENDING_REVIEW: lambda db, d, _a: _handle_pending_review(d),
}


def apply_single(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int] = None,
) -> ApplyResult:
    handler = _ACTION_HANDLERS.get(decision.merged_action)
    if handler is not None:
        return handler(db, decision, actor_id)
    return ApplyResult(
        target_kind=decision.target_kind,
        target_id=decision.target_id,
        action=decision.merged_action,
        success=False,
        error=f"Unknown action: {decision.merged_action}",
    )


def _ensure_target_exists(db: Session, target_id: int) -> Optional[TestCase]:
    return db.query(TestCase).filter(TestCase.id == target_id, TestCase.is_deleted.is_(False)).first()


def _build_result(
    decision: ApplyDecision,
    success: bool,
    new_case_id: Optional[int] = None,
    error: Optional[str] = None,
) -> ApplyResult:
    return ApplyResult(
        target_kind=decision.target_kind,
        target_id=decision.target_id,
        action=decision.merged_action,
        success=success,
        new_case_id=new_case_id,
        error=error,
    )


def _handle_keep(decision: ApplyDecision) -> ApplyResult:
    return _build_result(decision, success=True)


def _handle_needs_modify(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int],
) -> ApplyResult:
    target_id = decision.target_id
    if target_id is None:
        return _build_result(decision, success=False, error="target_id is required for needs_modify")
    case = _ensure_target_exists(db, target_id)
    if case is None:
        return _build_result(decision, success=False, error=f"TestCase id={target_id} not found")
    if decision.review_id is None:
        return _build_result(decision, success=False, error="review_id is required for needs_modify")
    try:
        lifecycle_transition(
            db, case_id=target_id, to_status="needs_modify",
            review_id=decision.review_id, modification_hint=decision.modification_hint,
            actor_id=actor_id,
        )
        return _build_result(decision, success=True)
    except (IllegalStateTransition, MissingReviewError) as e:
        logger.warning("needs_modify 业务校验失败: {}", e)
        return _build_result(decision, success=False, error="业务校验失败，请检查 review_id")


def _handle_locator_broken(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int],
) -> ApplyResult:
    target_id = decision.target_id
    if target_id is None:
        return _build_result(decision, success=False, error="target_id is required for locator_broken")
    case = _ensure_target_exists(db, target_id)
    if case is None:
        return _build_result(decision, success=False, error=f"TestCase id={target_id} not found")
    try:
        lifecycle_transition(db, case_id=target_id, to_status="locator_broken", actor_id=actor_id)
        return _build_result(decision, success=True)
    except IllegalStateTransition as e:
        logger.warning("locator_broken 状态转换失败: {}", e)
        return _build_result(decision, success=False, error="状态转换不合法")
