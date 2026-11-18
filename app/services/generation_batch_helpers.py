import asyncio

"""生成批次共享常量与业务工具（R2-3：从 `endpoints/_generation_batch_helpers.py` 下沉）。

职责：状态迁移校验、批次号生成、ORM→响应转换，以及「版本快照 / 用例废弃」两个
跨表业务动作。均以同步 `Session` 入参（R2-1），不自行建会话。
"""
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.generation_batch import GenerationBatch
from app.schemas.generation_batch import GenerationBatchResponse
from app.services.lifecycle_service import transition as lifecycle_transition

VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"context_ready", "failed"},
    "context_ready": {"generating", "failed"},
    "generating": {"preview_ready", "failed"},
    "preview_ready": {"saving", "generating"},
    "saving": {"saved", "partial_saved", "failed"},
    "partial_saved": {"saving"},
    "failed": {"context_ready", "generating"},
    "saved": set(),
}


def _validate_status_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批次状态不允许从 {current} 转换到 {target}，允许的目标状态: {allowed or '无（终态）'}",
        )


def _generate_batch_no(project_id: int) -> str:
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S%f")
    return f"GB{date_str}{time_str}{project_id:04d}"


def _batch_to_response(batch: GenerationBatch) -> dict:
    return GenerationBatchResponse(
        id=batch.id,
        batch_no=batch.batch_no,
        project_id=batch.project_id,
        user_id=batch.user_id,
        entry_type=batch.entry_type,
        scenario_type=batch.scenario_type,
        generation_strategy=batch.generation_strategy,
        status=batch.status,
        requirement_file_ids=batch.requirement_file_ids_json or [],
        test_point_ids=batch.test_point_ids_json or [],
        ui_screen_ids=batch.ui_screen_ids_json or [],
        history_asset_ids=batch.history_asset_ids_json or [],
        context_stats=batch.context_stats_json or {},
        warnings=batch.warnings_json or [],
        evidence_refs=batch.evidence_refs_json or {},
        quality_summary=batch.quality_summary_json or {},
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    ).model_dump()


async def _create_case_version_snapshot(
    db: Session,
    case_id: int,
    change_type: str,
    operator_id: int,
    change_description: str,
    changed_fields: dict | None = None,
) -> None:
    """创建用例版本快照（sync 依赖经 asyncio.to_thread 转线程池）。

    跳过自动版本快照事件，由 CaseVersionService 手动创建。
    """
    from app.models.test_case import skip_version_snapshot, resume_version_snapshot
    from app.services.case_version_service import CaseVersionService

    skip_version_snapshot()
    try:

        def _sync_snapshot(sync_db):
            return CaseVersionService.create_snapshot(
                db=sync_db,
                test_case_id=case_id,
                change_type=change_type,
                operator_id=operator_id,
                change_description=change_description,
                changed_fields=changed_fields,
            )

        await asyncio.to_thread(_sync_snapshot, db)
    finally:
        resume_version_snapshot()


async def _deprecate_case(db: Session, case_id: int, actor_id: int, reason: str) -> None:
    """通过 lifecycle_service 标记用例为 deprecated（sync 依赖经 asyncio.to_thread 转线程池）。"""

    def _sync_lifecycle(sync_db):
        lifecycle_transition(
            db=sync_db,
            case_id=case_id,
            to_status="deprecated",
            actor_id=actor_id,
            reason=reason,
        )

    await asyncio.to_thread(_sync_lifecycle, db)
