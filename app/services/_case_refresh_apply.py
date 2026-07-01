"""case_refresh 应用建议子模块。

从 case_refresh_service.py 拆分而来，包含审核与应用保鲜建议的
核心写操作：review_suggestion 编排审核动作，apply_suggestion 执行
建议应用（更新用例字段或废弃），create_version_snapshot 在应用前
创建版本快照。所有函数均为模块级纯函数，接受 db 参数。

业务原因：case_refresh_service.py 单文件超过 350 行限制，按职责将
应用建议相关逻辑集中到独立文件，主服务类聚焦于查询与扫描编排。
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.case_refresh_suggestion import CaseRefreshSuggestion
from app.models.test_case import (
    TestCase,
    enable_lifecycle_transition,
    disable_lifecycle_transition,
)
from app.services.lifecycle_service._service import transition as lifecycle_transition


def review_suggestion(
    db: Session,
    suggestion_id: int,
    action: str,
    reviewer_id: int,
    reviewer_name: str,
    reject_reason: Optional[str] = None,
) -> CaseRefreshSuggestion:
    suggestion = db.query(CaseRefreshSuggestion).filter(
        CaseRefreshSuggestion.id == suggestion_id,
    ).first()
    if not suggestion:
        raise ValueError(f"保鲜建议不存在: {suggestion_id}")
    if suggestion.review_status != "pending":
        raise ValueError(f"保鲜建议已审核: {suggestion.review_status}")

    suggestion.reviewer_id = reviewer_id
    suggestion.reviewer_name = reviewer_name
    suggestion.reviewed_at = datetime.now(timezone.utc)

    if action == "approve":
        suggestion.review_status = "approved"
        apply_suggestion(db, suggestion)
    elif action == "reject":
        suggestion.review_status = "rejected"
        suggestion.reject_reason = reject_reason or ""
        suggestion.suggestion_status = "rejected"
    else:
        raise ValueError(f"无效的审核操作: {action}")

    db.flush()
    return suggestion


def apply_suggestion(db: Session, suggestion: CaseRefreshSuggestion) -> int:
    case = db.query(TestCase).filter(TestCase.id == suggestion.case_id).first()
    if not case:
        suggestion.failure_reason = f"关联用例不存在: {suggestion.case_id}"
        suggestion.suggestion_status = "expired"
        return 0

    version_id = create_version_snapshot(db, case, "refresh_apply")
    suggestion.snapshot_version_id = version_id

    if suggestion.deprecation_reason and not suggestion.suggested_title:
        enable_lifecycle_transition()
        try:
            lifecycle_transition(
                db=db,
                case_id=case.id,
                to_status="deprecated",
                actor_id=suggestion.reviewer_id,
                reason=suggestion.deprecation_reason,
            )
        finally:
            disable_lifecycle_transition()
        suggestion.suggestion_status = "applied"
        return version_id

    if suggestion.suggested_title:
        case.title = suggestion.suggested_title
    if suggestion.suggested_expected_result:
        case.expected_result = suggestion.suggested_expected_result
    if suggestion.suggested_steps:
        case.steps_json = suggestion.suggested_steps
        from app.models.test_case import TestStep
        db.query(TestStep).filter(TestStep.test_case_id == case.id).delete()
        for idx, step_data in enumerate(suggestion.suggested_steps):
            if isinstance(step_data, dict):
                step = TestStep(
                    test_case_id=case.id,
                    step_number=idx + 1,
                    action=step_data.get("action", step_data.get("description", "")),
                    expected_result=step_data.get("expected_result", ""),
                    action_type=step_data.get("action_type"),
                    input_value=step_data.get("input_value", ""),
                    target_element=step_data.get("target_element", ""),
                )
                db.add(step)

    suggestion.suggestion_status = "applied"
    return version_id


def create_version_snapshot(db: Session, case: TestCase, change_type: str) -> int:
    from app.services.case_version_service import CaseVersionService
    from app.models.test_case import skip_version_snapshot, resume_version_snapshot

    skip_version_snapshot()
    try:
        version = CaseVersionService.create_snapshot(
            db=db,
            test_case_id=case.id,
            change_type=change_type,
            change_description="保鲜建议应用前自动快照",
        )
    finally:
        resume_version_snapshot()

    return version.id if version else 0


__all__ = [
    "review_suggestion",
    "apply_suggestion",
    "create_version_snapshot",
]
