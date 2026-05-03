"""
决策应用服务

评审 finalize 后，将人工决策应用到用例库：更新 lifecycle_status、创建新版本。

核心类/函数概览：
    - ApplyDecision : 决策输入 dataclass
    - ApplyResult : 决策应用结果 dataclass
    - apply_decisions(db, decisions) -> list[ApplyResult] : 批量应用决策
    - apply_single(db, decision) -> ApplyResult : 单个应用决策

依赖关系：
    - app.services.lifecycle_service : 状态迁移
    - app.pipelines.steps.reconciliation.MergedAction : 合并动作枚举
    - app.models.test_case.TestCase : ORM 模型
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List

from sqlalchemy.orm import Session

from app.services.lifecycle_service import transition as lifecycle_transition
from app.services.lifecycle_service import (
    IllegalStateTransition,
    MissingReviewError,
    MissingDeprecateReasonError,
)
from app.pipelines.steps.reconciliation import MergedAction
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition

logger = logging.getLogger(__name__)


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
    decisions: List[ApplyDecision],
    actor_id: Optional[int] = None,
) -> List[ApplyResult]:
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
    MergedAction.ADD_NEW: lambda db, d, _a: _handle_add_new(d),
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
    return db.query(TestCase).filter(TestCase.id == target_id).first()


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
            db,
            case_id=target_id,
            to_status="needs_modify",
            review_id=decision.review_id,
            modification_hint=decision.modification_hint,
            actor_id=actor_id,
        )
        return _build_result(decision, success=True)
    except (IllegalStateTransition, MissingReviewError) as e:
        return _build_result(decision, success=False, error=str(e))


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
        lifecycle_transition(
            db,
            case_id=target_id,
            to_status="locator_broken",
            actor_id=actor_id,
        )
        return _build_result(decision, success=True)
    except IllegalStateTransition as e:
        return _build_result(decision, success=False, error=str(e))


def _handle_locator_and_modify(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int],
) -> ApplyResult:
    target_id = decision.target_id
    if target_id is None:
        return _build_result(decision, success=False, error="target_id is required for locator_and_modify")

    case = _ensure_target_exists(db, target_id)
    if case is None:
        return _build_result(decision, success=False, error=f"TestCase id={target_id} not found")

    try:
        lifecycle_transition(
            db,
            case_id=target_id,
            to_status="locator_broken",
            actor_id=actor_id,
        )
    except IllegalStateTransition as e:
        return _build_result(decision, success=False, error=str(e))

    if decision.review_id is None:
        return _build_result(decision, success=True)

    try:
        enable_lifecycle_transition()
        base_no = case.case_no.rsplit("-v", 1)[0] if "-v" in case.case_no else case.case_no
        parent_version = int(case.case_no.rsplit("-v", 1)[1]) if "-v" in case.case_no else 1
        new_case = TestCase(
            project_id=case.project_id,
            case_no=f"{base_no}-v{parent_version + 1}",
            module=case.module,
            title=case.title,
            precondition=case.precondition,
            steps_json=case.steps_json,
            expected_result=case.expected_result,
            priority=case.priority,
            case_type=case.case_type,
            exec_script=case.exec_script,
            test_category=case.test_category,
            generate_status=case.generate_status,
            lifecycle_status="pending_review",
            test_point_id=case.test_point_id,
            summary=case.summary,
            summary_version=case.summary_version,
            summary_model_version=case.summary_model_version,
            parent_case_id=case.id,
            last_review_id=decision.review_id,
        )
        db.add(new_case)
        db.flush()
        new_case_id = new_case.id
    except Exception as e:
        return _build_result(decision, success=False, error=f"创建新版本失败: {e}")
    finally:
        disable_lifecycle_transition()

    return _build_result(decision, success=True, new_case_id=new_case_id)


def _handle_deprecate(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int],
) -> ApplyResult:
    target_id = decision.target_id
    if target_id is None:
        return _build_result(decision, success=False, error="target_id is required for deprecate")

    case = _ensure_target_exists(db, target_id)
    if case is None:
        return _build_result(decision, success=False, error=f"TestCase id={target_id} not found")

    if decision.review_id is None:
        return _build_result(decision, success=False, error="review_id is required for deprecate")

    if not decision.deprecate_reason:
        return _build_result(decision, success=False, error="deprecate_reason is required for deprecate")

    try:
        lifecycle_transition(
            db,
            case_id=target_id,
            to_status="deprecated",
            review_id=decision.review_id,
            reason=decision.deprecate_reason,
            actor_id=actor_id,
        )
        return _build_result(decision, success=True)
    except (IllegalStateTransition, MissingReviewError, MissingDeprecateReasonError) as e:
        return _build_result(decision, success=False, error=str(e))


def _handle_add_new(decision: ApplyDecision) -> ApplyResult:
    if decision.case_data is None:
        return _build_result(
            decision,
            success=False,
            error="case_data is required for add_new",
        )
    return ApplyResult(
        target_kind=decision.target_kind,
        target_id=decision.target_id,
        action=decision.merged_action,
        success=True,
        deferred=True,
        deferred_reason="add_new requires test_case_service integration (deferred to M2-T11)",
    )


def _handle_conflict(decision: ApplyDecision) -> ApplyResult:
    return _build_result(
        decision,
        success=False,
        error="conflict requires manual resolution",
    )


def _handle_pending_review(decision: ApplyDecision) -> ApplyResult:
    return ApplyResult(
        target_kind=decision.target_kind,
        target_id=decision.target_id,
        action=decision.merged_action,
        success=True,
        deferred=True,
        deferred_reason="pending_review deferred for manual evaluation",
    )
