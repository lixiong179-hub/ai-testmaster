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
import hashlib
import json
import logging
import time
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


def _handle_add_new(
    db: Session,
    decision: ApplyDecision,
    actor_id: Optional[int],
) -> ApplyResult:
    """处理新增用例决策 -- 通过 Pipeline 内 CaseGeneration 生成新用例。

    创建 supplement Iteration 并触发场景4 Pipeline 重新执行，
    为新候选场景生成测试用例。

    Args:
        db: 数据库会话。
        decision: 决策输入，case_data 需包含 candidate_description / project_id 等。
        actor_id: 操作人 ID。

    Returns:
        ApplyResult: 执行成功时 success=True，失败时含 error 信息。
    """
    from app.models.iteration import Iteration, IterationInput
    from app.models.enums import IterationInputKind
    from app.pipelines.runner import PipelineRunner
    from app.pipelines.context import PipelineContext
    from app.pipelines.scenarios import get_scenario
    from app.ai.openai_client import OpenAIClient
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

        # 创建 supplement iteration，使用时间戳保证名称唯一
        iteration_name = f"supplement_add_new_{int(time.time() * 1000)}"
        iteration = Iteration(
            project_id=project_id,
            name=iteration_name,
            version="v1.0",
            description=candidate_desc,
            status="draft",
            created_by=actor_id,
        )
        db.add(iteration)
        db.flush()
        iteration_id = iteration.id

        # 创建 supplement_form 类型的 IterationInput，承载 candidate 信息
        payload_data = {
            "source": "add_new_decision",
            "review_id": review_id,
            "candidate_description": candidate_desc,
            "candidate_module": candidate_module,
            "decision_comment": decision.modification_hint or "",
            "case_data": case_data,
        }
        payload_hash = hashlib.sha256(
            json.dumps(payload_data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

        iteration_input = IterationInput(
            iteration_id=iteration_id,
            kind=IterationInputKind.SUPPLEMENT_FORM.value,
            payload=payload_data,
            content_hash=payload_hash,
        )
        db.add(iteration_input)
        db.flush()

        # 创建 PipelineRun
        input_hash = pipeline_service.compute_input_hash([iteration_input])
        scenario = get_scenario(4)
        if scenario is None:
            return _build_result(decision, success=False, error="场景4配置未注册")

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration_id,
            input_hash=input_hash,
            pipeline_version=scenario["version"],
        )
        db.flush()

        # 将迭代状态迁移为 in_pipeline
        iteration_service.transition_iteration_status(db, iteration_id, "in_pipeline")

        # 创建 AI Client 与 PipelineContext
        ai_client = OpenAIClient()
        ctx = PipelineContext(
            db=db,
            ai_client=ai_client,
            run=run,
            iteration_id=iteration_id,
            user_id=actor_id,
        )

        # 执行场景4 Pipeline
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        # 刷新 run 检查执行结果
        db.refresh(run)

        if run.status == "completed":
            persisted = ctx.get_artifact("persisted_case_ids")
            generated_count = 0
            if persisted and isinstance(persisted, dict):
                case_ids = persisted.get("case_ids", [])
                generated_count = len(case_ids) if isinstance(case_ids, list) else 0
            logger.info(
                "_handle_add_new 成功: iteration_id=%d, generated_count=%d",
                iteration_id, generated_count,
            )
            return ApplyResult(
                target_kind=decision.target_kind,
                target_id=decision.target_id,
                action=decision.merged_action,
                success=True,
            )
        else:
            error_msg = f"Pipeline 执行失败，状态: {run.status}"
            if run.error:
                error_msg += f"，错误: {run.error}"
            logger.error("_handle_add_new Pipeline 失败: %s", error_msg)
            return _build_result(decision, success=False, error=error_msg)

    except Exception as e:
        logger.error("_handle_add_new 失败: %s", e, exc_info=True)
        return _build_result(decision, success=False, error=f"add_new 处理异常: {str(e)}")


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
