"""case_refresh 应用建议子模块（async 版本）。

从 case_refresh_service.py 拆分而来，包含审核与应用保鲜建议的
核心写操作：review_suggestion 编排审核动作，apply_suggestion 执行
建议应用（更新用例字段或废弃），create_version_snapshot 在应用前
创建版本快照。所有函数均为模块级纯函数，接受 AsyncSession 参数。

业务原因：case_refresh_service.py 单文件超过 350 行限制，按职责将
应用建议相关逻辑集中到独立文件，主服务类聚焦于查询与扫描编排。

迁移说明（P0 服务 async 化）:
    所有 DB 查询已改为 select() + await db.execute() 模式。
    对 sync 依赖（lifecycle_transition / CaseVersionService.create_snapshot）
    使用 db.run_sync() 桥接，避免越界迁移外部服务。
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_refresh_suggestion import CaseRefreshSuggestion
from app.models.test_case import (
    TestCase,
    enable_lifecycle_transition,
    disable_lifecycle_transition,
    TestStep,
)


async def review_suggestion(
    db: AsyncSession,
    suggestion_id: int,
    action: str,
    reviewer_id: int,
    reviewer_name: str,
    reject_reason: Optional[str] = None,
) -> CaseRefreshSuggestion:
    """审核保鲜建议，根据动作应用或驳回。

    Args:
        db: 异步数据库会话。
        suggestion_id: 保鲜建议ID。
        action: 审核动作（approve/reject）。
        reviewer_id: 审核人ID。
        reviewer_name: 审核人姓名。
        reject_reason: 驳回原因（仅 reject 时有效）。

    Returns:
        更新后的保鲜建议实例。

    Raises:
        ValueError: 建议不存在或已审核、动作非法时抛出。
    """
    result = await db.execute(
        select(CaseRefreshSuggestion).where(
            CaseRefreshSuggestion.id == suggestion_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise ValueError(f"保鲜建议不存在: {suggestion_id}")
    if suggestion.review_status != "pending":
        raise ValueError(f"保鲜建议已审核: {suggestion.review_status}")

    suggestion.reviewer_id = reviewer_id
    suggestion.reviewer_name = reviewer_name
    suggestion.reviewed_at = datetime.now(timezone.utc)

    if action == "approve":
        suggestion.review_status = "approved"
        await apply_suggestion(db, suggestion)
    elif action == "reject":
        suggestion.review_status = "rejected"
        suggestion.reject_reason = reject_reason or ""
        suggestion.suggestion_status = "rejected"
    else:
        raise ValueError(f"无效的审核操作: {action}")

    await db.flush()
    return suggestion


async def apply_suggestion(db: AsyncSession, suggestion: CaseRefreshSuggestion) -> int:
    """应用保鲜建议，更新用例字段或标记废弃。

    业务边界：若关联用例不存在，将建议标记为 expired 而非抛异常，
    避免阻塞批量审核流程。

    Args:
        db: 异步数据库会话。
        suggestion: 待应用的保鲜建议。

    Returns:
        版本快照ID，若用例不存在则返回 0。
    """
    result = await db.execute(
        select(TestCase).where(TestCase.id == suggestion.case_id)
    )
    case = result.scalar_one_or_none()
    if not case:
        suggestion.failure_reason = f"关联用例不存在: {suggestion.case_id}"
        suggestion.suggestion_status = "expired"
        return 0

    version_id = await create_version_snapshot(db, case, "refresh_apply")
    suggestion.snapshot_version_id = version_id

    if suggestion.deprecation_reason and not suggestion.suggested_title:
        enable_lifecycle_transition()
        try:
            # lifecycle_transition 为 sync 外部依赖，使用 run_sync 桥接
            def _sync_lifecycle(sync_db):
                from app.services.lifecycle_service._service import transition as lifecycle_transition
                lifecycle_transition(
                    db=sync_db,
                    case_id=case.id,
                    to_status="deprecated",
                    actor_id=suggestion.reviewer_id,
                    reason=suggestion.deprecation_reason,
                )
            await db.run_sync(_sync_lifecycle)
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
        await db.execute(
            delete(TestStep).where(TestStep.test_case_id == case.id)
        )
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


async def create_version_snapshot(
    db: AsyncSession, case: TestCase, change_type: str
) -> int:
    """创建用例版本快照（应用建议前自动快照）。

    使用 skip_version_snapshot 上下文避免快照事件递归触发。

    Args:
        db: 异步数据库会话。
        case: 待快照的用例。
        change_type: 变更类型。

    Returns:
        版本快照ID，若创建失败返回 0。
    """
    from app.services.case_version_service import CaseVersionService
    from app.models.test_case import skip_version_snapshot, resume_version_snapshot

    skip_version_snapshot()
    try:
        # CaseVersionService.create_snapshot 为 sync 外部依赖，使用 run_sync 桥接
        def _sync_snapshot(sync_db):
            return CaseVersionService.create_snapshot(
                db=sync_db,
                test_case_id=case.id,
                change_type=change_type,
                change_description="保鲜建议应用前自动快照",
            )
        version = await db.run_sync(_sync_snapshot)
    finally:
        resume_version_snapshot()

    return version.id if version else 0


__all__ = [
    "review_suggestion",
    "apply_suggestion",
    "create_version_snapshot",
]
