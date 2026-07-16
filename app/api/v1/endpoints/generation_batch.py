import hashlib
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.generation_batch import GenerationBatch, GenerationBatchSave
from app.models.project import Project, ProjectFile
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.services.case_number_service import CaseNumberService
from app.services.lifecycle_service import transition as lifecycle_transition
from app.schemas.generation_batch import (
    BatchSaveFailureItem,
    GenerationBatchCreate,
    GenerationBatchResponse,
    GenerationBatchSaveRequest,
    GenerationBatchSaveResponse,
    GenerationBatchUpdate,
)
from app.utils.db_time import utcnow
from app.schemas.common import ApiResponse

router = APIRouter(tags=["生成批次"])

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


@router.post("", response_model=ApiResponse)
async def create_generation_batch(
    body: GenerationBatchCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """创建生成批次。"""
    project_result = await db.execute(
        select(Project).where(
            Project.id == body.project_id, Project.user_id == current_user.id
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限"
        )

    batch = GenerationBatch(
        batch_no=_generate_batch_no(body.project_id),
        project_id=body.project_id,
        user_id=current_user.id,
        entry_type=body.entry_type,
        scenario_type=body.scenario_type,
        generation_strategy=body.generation_strategy,
        status="created",
        requirement_file_ids_json=body.requirement_file_ids,
        test_point_ids_json=body.test_point_ids,
        ui_screen_ids_json=body.ui_screen_ids,
        history_asset_ids_json=body.history_asset_ids,
        client_request_id=body.client_request_id,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return create_response(data=_batch_to_response(batch))


@router.get("/{batch_id}", response_model=ApiResponse)
async def get_generation_batch(
    batch_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """获取生成批次详情。"""
    batch_result = await db.execute(
        select(GenerationBatch).where(GenerationBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在"
        )
    if batch.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此批次"
        )
    return create_response(data=_batch_to_response(batch))


@router.patch("/{batch_id}", response_model=ApiResponse)
async def update_generation_batch(
    batch_id: int,
    body: GenerationBatchUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """更新生成批次状态与上下文统计。"""
    batch_result = await db.execute(
        select(GenerationBatch).where(GenerationBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在"
        )
    if batch.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此批次"
        )

    if body.status is not None:
        _validate_status_transition(batch.status, body.status)
        batch.status = body.status

    if body.context_stats is not None:
        batch.context_stats_json = body.context_stats
    if body.warnings is not None:
        batch.warnings_json = body.warnings
    if body.evidence_refs is not None:
        batch.evidence_refs_json = body.evidence_refs
    if body.quality_summary is not None:
        batch.quality_summary_json = body.quality_summary

    batch.updated_at = utcnow()
    await db.commit()
    await db.refresh(batch)
    return create_response(data=_batch_to_response(batch))


async def _create_case_version_snapshot(
    db: AsyncSession,
    case_id: int,
    change_type: str,
    operator_id: int,
    change_description: str,
    changed_fields: dict | None = None,
) -> None:
    """创建用例版本快照（sync 依赖通过 run_sync 桥接）。

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
        await db.run_sync(_sync_snapshot)
    finally:
        resume_version_snapshot()


async def _deprecate_case(
    db: AsyncSession, case_id: int, actor_id: int, reason: str
) -> None:
    """通过 lifecycle_service 标记用例为 deprecated（sync 依赖通过 run_sync 桥接）。"""
    def _sync_lifecycle(sync_db):
        lifecycle_transition(
            db=sync_db,
            case_id=case_id,
            to_status="deprecated",
            actor_id=actor_id,
            reason=reason,
        )
    await db.run_sync(_sync_lifecycle)


@router.post("/{batch_id}/save", response_model=ApiResponse)
async def save_generation_batch(
    batch_id: int,
    body: GenerationBatchSaveRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """保存批次预览用例（支持新增/更新/废弃，幂等键防重）。"""
    batch_result = await db.execute(
        select(GenerationBatch).where(GenerationBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在"
        )
    if batch.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此批次"
        )

    existing_save_result = await db.execute(
        select(GenerationBatchSave).where(
            GenerationBatchSave.batch_id == batch_id,
            GenerationBatchSave.idempotency_key == body.idempotency_key,
        )
    )
    existing_save = existing_save_result.scalar_one_or_none()
    if existing_save:
        new_hash = hashlib.sha256(
            json.dumps(
                {"save_mode": body.save_mode, "cases": body.cases},
                default=str, ensure_ascii=False,
            ).encode()
        ).hexdigest()
        if existing_save.request_hash and existing_save.request_hash != new_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="幂等键已存在但请求内容不一致，请更换 idempotency_key",
            )
        return create_response(data=existing_save.result_json)

    _validate_status_transition(batch.status, "saving")
    batch.status = "saving"
    await db.flush()

    request_hash = hashlib.sha256(
        json.dumps(
            {"save_mode": body.save_mode, "cases": body.cases},
            default=str, ensure_ascii=False,
        ).encode()
    ).hexdigest()

    saved_case_ids: list[int] = []
    failures: list[BatchSaveFailureItem] = []

    lifecycle_status = "draft" if body.save_mode == "draft" else "active"

    cases_to_save = body.cases
    if body.save_mode == "passed_only":
        cases_to_save = [
            c for c in cases_to_save
            if c.quality_status in ("passed", "warning") and c.selected_for_save
        ]
    else:
        cases_to_save = [c for c in cases_to_save if c.selected_for_save]

    all_req_file_ids = set()
    for c in cases_to_save:
        if c.requirement_file_id:
            all_req_file_ids.add(c.requirement_file_id)
        if c.source_refs:
            refs = c.source_refs
            if "requirement_file_id" in refs and isinstance(refs["requirement_file_id"], int):
                all_req_file_ids.add(refs["requirement_file_id"])
            if "requirement_file_ids" in refs and isinstance(refs["requirement_file_ids"], list):
                for rid in refs["requirement_file_ids"]:
                    if isinstance(rid, int):
                        all_req_file_ids.add(rid)
    for rid in batch.requirement_file_ids_json or []:
        if isinstance(rid, int):
            all_req_file_ids.add(rid)
    if all_req_file_ids:
        valid_files_result = await db.execute(
            select(ProjectFile.id).where(
                ProjectFile.id.in_(all_req_file_ids),
                ProjectFile.project_id == batch.project_id,
                ProjectFile.resource_type == "requirement",
            )
        )
        valid_ids = set(valid_files_result.scalars().all())
        invalid_ids = all_req_file_ids - valid_ids
        if invalid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"以下需求文件ID不属于当前项目或不是需求类型: {sorted(invalid_ids)}",
            )

    for idx, case_payload in enumerate(cases_to_save):
        try:
            async with db.begin_nested():
                if case_payload.update_action == "update_existing" and case_payload.history_case_id:
                    existing_case_result = await db.execute(
                        select(TestCase).where(
                            TestCase.id == case_payload.history_case_id,
                            TestCase.project_id == batch.project_id,
                            TestCase.is_deleted.is_(False),
                        )
                    )
                    existing_case = existing_case_result.scalar_one_or_none()
                    if not existing_case:
                        raise ValueError(
                            f"用例ID={case_payload.history_case_id}不存在或不属于当前项目"
                        )

                    await _create_case_version_snapshot(
                        db=db,
                        case_id=existing_case.id,
                        change_type="update",
                        operator_id=batch.user_id,
                        change_description=f"历史资产更新批次 {batch.batch_no} 触发更新",
                        changed_fields=case_payload.diff_fields if case_payload.diff_fields else None,
                    )

                    existing_case.title = case_payload.title
                    existing_case.module = case_payload.module or existing_case.module
                    existing_case.precondition = case_payload.precondition or existing_case.precondition
                    existing_case.expected_result = case_payload.expected_result or existing_case.expected_result
                    if case_payload.priority:
                        existing_case.priority = case_payload.priority
                    if case_payload.steps:
                        steps_list = [step.model_dump() for step in case_payload.steps]
                        existing_case.steps_json = steps_list
                        await db.execute(
                            delete(TestStep).where(TestStep.test_case_id == existing_case.id)
                        )
                        for step_idx, step_data in enumerate(case_payload.steps):
                            test_step = TestStep(
                                test_case_id=existing_case.id,
                                step_number=step_idx + 1,
                                action=step_data.action or "",
                                expected_result=step_data.expected_result or "",
                                action_type=step_data.action_type,
                                input_value=step_data.input_value,
                                target_element=step_data.target_element,
                                is_business_view=1,
                                is_technical_view=1,
                            )
                            db.add(test_step)

                    await db.flush()
                    saved_case_ids.append(existing_case.id)
                elif case_payload.update_action == "deprecate" and case_payload.history_case_id:
                    existing_case_result = await db.execute(
                        select(TestCase).where(
                            TestCase.id == case_payload.history_case_id,
                            TestCase.project_id == batch.project_id,
                            TestCase.is_deleted.is_(False),
                        )
                    )
                    existing_case = existing_case_result.scalar_one_or_none()
                    if not existing_case:
                        raise ValueError(
                            f"用例ID={case_payload.history_case_id}不存在或不属于当前项目"
                        )

                    await _create_case_version_snapshot(
                        db=db,
                        case_id=existing_case.id,
                        change_type="update",
                        operator_id=batch.user_id,
                        change_description=f"历史资产更新批次 {batch.batch_no} 标记为可能废弃",
                        changed_fields={"lifecycle_status": {"old": existing_case.lifecycle_status, "new": "deprecated"}},
                    )
                    await db.flush()

                    await _deprecate_case(
                        db=db,
                        case_id=existing_case.id,
                        actor_id=batch.user_id,
                        reason=f"历史资产更新批次 {batch.batch_no} 标记为可能废弃",
                    )
                    await db.flush()
                    saved_case_ids.append(existing_case.id)
                else:
                    req_file_id = case_payload.requirement_file_id
                    if req_file_id is None and case_payload.source_refs:
                        refs = case_payload.source_refs
                        if "requirement_file_id" in refs:
                            req_file_id = refs["requirement_file_id"]
                        elif "requirement_file_ids" in refs and isinstance(refs["requirement_file_ids"], list) and refs["requirement_file_ids"]:
                            req_file_id = refs["requirement_file_ids"][0]
                    if req_file_id is None:
                        req_ids = batch.requirement_file_ids_json or []
                        if req_ids:
                            req_file_id = req_ids[0]

                    steps_list = [step.model_dump() for step in case_payload.steps]
                    test_category = case_payload.case_category or ""

                    case_no = await CaseNumberService.generate_async(batch.project_id, db)

                    new_case = TestCase(
                        case_no=case_no,
                        project_id=batch.project_id,
                        requirement_file_id=req_file_id,
                        test_point_id=case_payload.source_test_point_id,
                        module=case_payload.module or "",
                        title=case_payload.title,
                        precondition=case_payload.precondition or "",
                        steps_json=steps_list,
                        expected_result=case_payload.expected_result or "",
                        priority=case_payload.priority,
                        case_type=case_payload.case_type or "manual",
                        test_category=test_category,
                        generate_status=1,
                        lifecycle_status=lifecycle_status,
                    )
                    db.add(new_case)
                    await db.flush()

                    for step_idx, step_data in enumerate(case_payload.steps):
                        test_step = TestStep(
                            test_case_id=new_case.id,
                            step_number=step_idx + 1,
                            action=step_data.action or "",
                            expected_result=step_data.expected_result or "",
                            action_type=step_data.action_type,
                            input_value=step_data.input_value,
                            target_element=step_data.target_element,
                            is_business_view=1,
                            is_technical_view=1,
                        )
                        db.add(test_step)

                    await db.flush()
                    saved_case_ids.append(new_case.id)
        except Exception as e:
            logger.warning(f"batch save 单条用例保存失败: {e}")
            failures.append(BatchSaveFailureItem(
                client_id=case_payload.client_id,
                title=case_payload.title,
                reason=str(e)[:500],
            ))

    total = len(cases_to_save)
    saved_count = len(saved_case_ids)
    failed_count = len(failures)

    if saved_count == 0:
        batch_status = "failed"
    elif failed_count > 0:
        batch_status = "partial_saved"
    else:
        batch_status = "saved"

    batch.status = batch_status
    batch.updated_at = utcnow()

    save_result = GenerationBatchSaveResponse(
        batch_id=batch_id,
        idempotency_key=body.idempotency_key,
        save_mode=body.save_mode,
        saved_count=saved_count,
        failed_count=failed_count,
        saved_case_ids=saved_case_ids,
        failures=failures,
        status=batch_status,
    ).model_dump()

    batch_save_record = GenerationBatchSave(
        batch_id=batch_id,
        idempotency_key=body.idempotency_key,
        save_mode=body.save_mode,
        request_hash=request_hash,
        result_json=save_result,
    )
    db.add(batch_save_record)
    await db.commit()

    return create_response(data=save_result)
