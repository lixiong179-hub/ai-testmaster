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
from app.services.decision_application_service._core import (
    ApplyDecision,
    ApplyResult,
    _build_result,
    _ensure_target_exists,
)


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
        lifecycle_transition(db, case_id=target_id, to_status="locator_broken", actor_id=actor_id)
    except IllegalStateTransition as e:
        logger.warning("locator_and_modify 状态转换失败: {}", e)
        return _build_result(decision, success=False, error="状态转换不合法")
    if decision.review_id is None:
        return _build_result(decision, success=True)
    try:
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
        enable_lifecycle_transition()
        try:
            db.add(new_case)
            db.flush()
        finally:
            disable_lifecycle_transition()
        new_case_id = new_case.id
    except Exception as e:
        logger.error("locator_and_modify 创建新版本失败: {}", e, exc_info=True)
        return _build_result(decision, success=False, error="创建新版本失败，详情见日志")
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
            db, case_id=target_id, to_status="deprecated",
            review_id=decision.review_id, reason=decision.deprecate_reason,
            actor_id=actor_id,
        )
        return _build_result(decision, success=True)
    except (IllegalStateTransition, MissingReviewError, MissingDeprecateReasonError) as e:
        logger.warning("deprecate 业务校验失败: {}", e)
        return _build_result(decision, success=False, error="业务校验失败，请检查 review_id 与 deprecate_reason")


def _handle_add_new(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int],
) -> ApplyResult:
    import hashlib
    import json
    import time

    from app.models.iteration import Iteration, IterationInput
    from app.models.enums import IterationInputKind
    from app.pipelines.runner import PipelineRunner
    from app.pipelines.context import PipelineContext
    from app.pipelines.scenarios import get_scenario
    from app.api.v1.endpoints.pipeline_resume import create_ai_client
    from app.services import pipeline_service, iteration_service

    case_data = decision.case_data or {}
    candidate_desc = case_data.get("candidate_description", "") or case_data.get("title", "")
    candidate_module = case_data.get("candidate_module", "") or case_data.get("module", "")
    project_id_raw = case_data.get("project_id")
    review_id = decision.review_id or case_data.get("review_id", "")

    if project_id_raw is None:
        return _build_result(decision, success=False, error="add_new 缺少 project_id")

    try:
        project_id = int(project_id_raw)
        iteration_name = f"supplement_add_new_{int(time.time() * 1000)}"
        iteration = Iteration(
            project_id=project_id, name=iteration_name, version="v1.0",
            description=candidate_desc, status="draft", created_by=actor_id,
        )
        db.add(iteration)
        db.flush()
        iteration_id = iteration.id

        payload_data = {
            "source": "add_new_decision", "review_id": review_id,
            "candidate_description": candidate_desc, "candidate_module": candidate_module,
            "decision_comment": decision.modification_hint or "", "case_data": case_data,
        }
        payload_hash = hashlib.sha256(
            json.dumps(payload_data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        iteration_input = IterationInput(
            iteration_id=iteration_id,
            kind=IterationInputKind.SUPPLEMENT_FORM.value,
            payload=payload_data, content_hash=payload_hash,
        )
        db.add(iteration_input)
        db.flush()

        input_hash = pipeline_service.compute_input_hash([iteration_input])
        scenario = get_scenario(4)
        if scenario is None:
            return _build_result(decision, success=False, error="场景4配置未注册")
        run = pipeline_service.create_run(
            db=db, iteration_id=iteration_id, input_hash=input_hash,
            pipeline_version=scenario["version"],
        )
        db.flush()
        iteration_service.transition_iteration_status(db, iteration_id, "in_pipeline")

        ai_client = create_ai_client()
        ctx = PipelineContext(
            db=db, ai_client=ai_client, run=run,
            iteration_id=iteration_id, user_id=actor_id,
        )
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)
        db.refresh(run)

        if run.status == "completed":
            persisted = ctx.get_artifact("persisted_case_ids")
            generated_count = 0
            if persisted and isinstance(persisted, dict):
                case_ids = persisted.get("case_ids", [])
                generated_count = len(case_ids) if isinstance(case_ids, list) else 0
            logger.info("_handle_add_new 成功: iteration_id={}, generated_count={}", iteration_id, generated_count)
            return ApplyResult(
                target_kind=decision.target_kind, target_id=decision.target_id,
                action=decision.merged_action, success=True,
            )
        else:
            error_msg = f"Pipeline 执行失败，状态: {run.status}"
            if run.error:
                error_msg += f"，错误: {run.error}"
            logger.error("_handle_add_new Pipeline 失败: {}", error_msg)
            return _build_result(decision, success=False, error=error_msg)
    except Exception as e:
        logger.error("_handle_add_new 失败: {}", e, exc_info=True)
        return _build_result(decision, success=False, error="add_new 处理失败，详情见日志")


def _handle_conflict(decision: ApplyDecision) -> ApplyResult:
    return _build_result(decision, success=False, error="conflict requires manual resolution")


def _handle_pending_review(decision: ApplyDecision) -> ApplyResult:
    return ApplyResult(
        target_kind=decision.target_kind, target_id=decision.target_id,
        action=decision.merged_action, success=True,
        deferred=True, deferred_reason="pending_review deferred for manual evaluation",
    )


def _load_decisions_from_review(review_id: int, db: Session) -> List[ApplyDecision]:
    from app.models.review import IterationReview, ReviewDecision
    review = db.get(IterationReview, review_id)
    if review is None:
        return []
    review_decisions = db.query(ReviewDecision).filter(
        ReviewDecision.review_id == review_id,
    ).all()
    result: List[ApplyDecision] = []
    for rd in review_decisions:
        merged_action = _verdict_to_action(rd.final_verdict, rd.conflict_marker)
        ad = ApplyDecision(
            target_kind=rd.target_kind, target_id=rd.target_id,
            merged_action=merged_action, modification_hint=rd.modification_hint,
            deprecate_reason=rd.deprecate_reason,
            confidence=rd.ai_confidence / 100.0 if rd.ai_confidence is not None else 0.0,
            review_id=review_id,
        )
        result.append(ad)
    return result


def _verdict_to_action(verdict: str, conflict: bool) -> str:
    if conflict:
        return MergedAction.CONFLICT
    mapping = {
        "keep": MergedAction.KEEP,
        "modify": MergedAction.NEEDS_MODIFY,
        "deprecate": MergedAction.DEPRECATE,
    }
    return mapping.get(verdict, MergedAction.PENDING_REVIEW)
