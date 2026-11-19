"""generation_batch 端点模块。

路由处理函数直接内联在本文件中；纯工具函数下沉至：
    - app/services/generation_batch_helpers.py  常量与纯工具函数

公开符号通过本文件 re-export，保持 import 路径不变。
"""

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import get_db
from app.models.generation_batch import GenerationBatch, GenerationBatchSave
from app.models.project import Project, ProjectFile
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.generation_batch import (
    BatchSaveFailureItem,
    GenerationBatchCreate,
    GenerationBatchSaveRequest,
    GenerationBatchSaveResponse,
    GenerationBatchUpdate,
)
from app.services.case_number_service import CaseNumberService
from app.services.generation_batch_helpers import (
    VALID_TRANSITIONS,
    _batch_to_response,
    _create_case_version_snapshot,
    _deprecate_case,
    _generate_batch_no,
    _validate_status_transition,
)
from app.utils.db_time import utcnow


async def create_generation_batch(
    body: GenerationBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建生成批次。"""
    project_result = await _execute(
        db, select(Project).where(Project.id == body.project_id, Project.user_id == current_user.id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限")

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
    await asyncio.to_thread(db.commit)
    await asyncio.to_thread(db.refresh, batch)
    return create_response(data=_batch_to_response(batch))


async def get_generation_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取生成批次详情。"""
    batch_result = await _execute(db, select(GenerationBatch).where(GenerationBatch.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")
    if batch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此批次")
    return create_response(data=_batch_to_response(batch))


async def update_generation_batch(
    batch_id: int,
    body: GenerationBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新生成批次状态与上下文统计。"""
    batch_result = await _execute(db, select(GenerationBatch).where(GenerationBatch.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")
    if batch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此批次")

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
    await asyncio.to_thread(db.commit)
    await asyncio.to_thread(db.refresh, batch)
    return create_response(data=_batch_to_response(batch))


def _compute_request_hash(body: GenerationBatchSaveRequest) -> str:
    """幂等请求指纹：save_mode + cases 的稳定 JSON 摘要。"""
    return hashlib.sha256(
        json.dumps(
            {"save_mode": body.save_mode, "cases": body.cases},
            default=str,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


async def _lookup_idempotent_replay(db: Session, batch_id: int, body: GenerationBatchSaveRequest):
    """命中幂等键时返回历史结果；内容不一致则 409。"""
    existing_save_result = await _execute(
        db,
        select(GenerationBatchSave).where(
            GenerationBatchSave.batch_id == batch_id,
            GenerationBatchSave.idempotency_key == body.idempotency_key,
        ),
    )
    existing_save = existing_save_result.scalar_one_or_none()
    if not existing_save:
        return None
    if existing_save.request_hash and existing_save.request_hash != _compute_request_hash(body):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="幂等键已存在但请求内容不一致，请更换 idempotency_key",
        )
    return existing_save.result_json


def _filter_cases_to_save(cases: list, save_mode: str) -> list:
    """按保存模式过滤勾选用例（passed_only 额外要求质量通过）。"""
    if save_mode == "passed_only":
        return [c for c in cases if c.quality_status in ("passed", "warning") and c.selected_for_save]
    return [c for c in cases if c.selected_for_save]


def _extract_source_ref_file_ids(refs: dict) -> set[int]:
    """从 source_refs 提取单值 / 多值需求文件 ID。"""
    file_ids: set[int] = set()
    single_id = refs.get("requirement_file_id")
    if isinstance(single_id, int):
        file_ids.add(single_id)
    multi_ids = refs.get("requirement_file_ids")
    if isinstance(multi_ids, list):
        file_ids.update(rid for rid in multi_ids if isinstance(rid, int))
    return file_ids


def _collect_requirement_file_ids(cases_to_save: list, batch: GenerationBatch) -> set[int]:
    """收集用例与批次引用的需求文件 ID。"""
    req_file_ids: set[int] = set()
    for c in cases_to_save:
        if c.requirement_file_id:
            req_file_ids.add(c.requirement_file_id)
        if c.source_refs:
            req_file_ids.update(_extract_source_ref_file_ids(c.source_refs))
    for rid in batch.requirement_file_ids_json or []:
        if isinstance(rid, int):
            req_file_ids.add(rid)
    return req_file_ids


async def _validate_requirement_ids(db: Session, batch: GenerationBatch, req_file_ids: set[int]) -> None:
    """校验需求文件均属当前项目且为 requirement 类型，否则 400。"""
    if not req_file_ids:
        return
    valid_files_result = await _execute(
        db,
        select(ProjectFile.id).where(
            ProjectFile.id.in_(req_file_ids),
            ProjectFile.project_id == batch.project_id,
            ProjectFile.resource_type == "requirement",
        ),
    )
    invalid_ids = req_file_ids - set(valid_files_result.scalars().all())
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下需求文件ID不属于当前项目或不是需求类型: {sorted(invalid_ids)}",
        )


def _first_requirement_ref(refs: dict):
    """source_refs 里的首选需求文件 ID。"""
    if "requirement_file_id" in refs:
        return refs["requirement_file_id"]
    multi_ids = refs.get("requirement_file_ids")
    if isinstance(multi_ids, list) and multi_ids:
        return multi_ids[0]
    return None


def _resolve_requirement_file_id(case_payload, batch: GenerationBatch):
    """按「用例指定 → source_refs → 批次默认」的顺序确定需求文件 ID。"""
    req_file_id = case_payload.requirement_file_id
    if req_file_id is None and case_payload.source_refs:
        req_file_id = _first_requirement_ref(case_payload.source_refs)
    if req_file_id is None:
        req_ids = batch.requirement_file_ids_json or []
        if req_ids:
            req_file_id = req_ids[0]
    return req_file_id


def _add_step_rows(db: Session, test_case_id: int, steps: list) -> None:
    """按顺序重建用例的 TestStep 行（业务/技术视图均可见）。"""
    for step_idx, step_data in enumerate(steps):
        db.add(
            TestStep(
                test_case_id=test_case_id,
                step_number=step_idx + 1,
                action=step_data.action or "",
                expected_result=step_data.expected_result or "",
                action_type=step_data.action_type,
                input_value=step_data.input_value,
                target_element=step_data.target_element,
                is_business_view=1,
                is_technical_view=1,
            )
        )


async def _load_batch_case(db: Session, batch: GenerationBatch, case_id: int):
    """查批次所属项目下的有效用例，不存在则抛 ValueError（计入单条失败）。"""
    result = await _execute(
        db,
        select(TestCase).where(
            TestCase.id == case_id,
            TestCase.project_id == batch.project_id,
            TestCase.is_deleted.is_(False),
        ),
    )
    existing_case = result.scalar_one_or_none()
    if not existing_case:
        raise ValueError(f"用例ID={case_id}不存在或不属于当前项目")
    return existing_case


async def _update_existing_case(db: Session, batch: GenerationBatch, case_payload) -> int:
    """update_existing：版本快照 + 字段覆盖 + 步骤重建。"""
    existing_case = await _load_batch_case(db, batch, case_payload.history_case_id)
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
        existing_case.steps_json = [step.model_dump() for step in case_payload.steps]
        await _execute(db, delete(TestStep).where(TestStep.test_case_id == existing_case.id))
        _add_step_rows(db, existing_case.id, case_payload.steps)

    await asyncio.to_thread(db.flush)
    return existing_case.id


async def _deprecate_existing_case(db: Session, batch: GenerationBatch, case_payload) -> int:
    """deprecate：版本快照 + 标记可能废弃。"""
    existing_case = await _load_batch_case(db, batch, case_payload.history_case_id)
    reason = f"历史资产更新批次 {batch.batch_no} 标记为可能废弃"
    await _create_case_version_snapshot(
        db=db,
        case_id=existing_case.id,
        change_type="update",
        operator_id=batch.user_id,
        change_description=reason,
        changed_fields={"lifecycle_status": {"old": existing_case.lifecycle_status, "new": "deprecated"}},
    )
    await asyncio.to_thread(db.flush)

    await _deprecate_case(
        db=db,
        case_id=existing_case.id,
        actor_id=batch.user_id,
        reason=reason,
    )
    await asyncio.to_thread(db.flush)
    return existing_case.id


async def _create_case_from_payload(db: Session, batch: GenerationBatch, case_payload, lifecycle_status: str) -> int:
    """新增用例：编号生成 + 主表写入 + 步骤重建。"""
    req_file_id = _resolve_requirement_file_id(case_payload, batch)
    case_no = await asyncio.to_thread(CaseNumberService.generate, batch.project_id, db)

    new_case = TestCase(
        case_no=case_no,
        project_id=batch.project_id,
        requirement_file_id=req_file_id,
        test_point_id=case_payload.source_test_point_id,
        module=case_payload.module or "",
        title=case_payload.title,
        precondition=case_payload.precondition or "",
        steps_json=[step.model_dump() for step in case_payload.steps],
        expected_result=case_payload.expected_result or "",
        priority=case_payload.priority,
        case_type=case_payload.case_type or "manual",
        test_category=case_payload.case_category or "",
        generate_status=1,
        lifecycle_status=lifecycle_status,
    )
    db.add(new_case)
    await asyncio.to_thread(db.flush)

    _add_step_rows(db, new_case.id, case_payload.steps)
    await asyncio.to_thread(db.flush)
    return new_case.id


async def _save_single_case(db: Session, batch: GenerationBatch, case_payload, lifecycle_status: str) -> int:
    """按 update_action 分派到更新 / 废弃 / 新增分支，返回用例 ID。"""
    if case_payload.update_action == "update_existing" and case_payload.history_case_id:
        return await _update_existing_case(db, batch, case_payload)
    if case_payload.update_action == "deprecate" and case_payload.history_case_id:
        return await _deprecate_existing_case(db, batch, case_payload)
    return await _create_case_from_payload(db, batch, case_payload, lifecycle_status)


def _resolve_batch_status(saved_count: int, failed_count: int) -> str:
    """批次终态：全失败 failed / 部分成功 partial_saved / 全成功 saved。"""
    if saved_count == 0:
        return "failed"
    if failed_count > 0:
        return "partial_saved"
    return "saved"


async def save_generation_batch(
    batch_id: int,
    body: GenerationBatchSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存批次预览用例（支持新增/更新/废弃，幂等键防重）。"""
    batch_result = await _execute(db, select(GenerationBatch).where(GenerationBatch.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")
    if batch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此批次")

    replay = await _lookup_idempotent_replay(db, batch_id, body)
    if replay is not None:
        return create_response(data=replay)

    _validate_status_transition(batch.status, "saving")
    batch.status = "saving"
    await asyncio.to_thread(db.flush)

    request_hash = _compute_request_hash(body)
    lifecycle_status = "draft" if body.save_mode == "draft" else "active"
    cases_to_save = _filter_cases_to_save(body.cases, body.save_mode)

    saved_case_ids: list[int] = []
    failures: list[BatchSaveFailureItem] = []

    await _validate_requirement_ids(db, batch, _collect_requirement_file_ids(cases_to_save, batch))

    for case_payload in cases_to_save:
        try:
            with db.begin_nested():
                saved_case_ids.append(await _save_single_case(db, batch, case_payload, lifecycle_status))
        except Exception as e:
            logger.warning(f"batch save 单条用例保存失败: {e}")
            failures.append(
                BatchSaveFailureItem(
                    client_id=case_payload.client_id,
                    title=case_payload.title,
                    reason=str(e)[:500],
                )
            )

    saved_count = len(saved_case_ids)
    failed_count = len(failures)

    batch_status = _resolve_batch_status(saved_count, failed_count)
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
    await asyncio.to_thread(db.commit)

    return create_response(data=save_result)


async def _execute(db: Session, stmt):
    """同步 Session 的查询在线程池执行，避免阻塞事件循环（R2-1）。"""
    return await asyncio.to_thread(db.execute, stmt)


router = APIRouter(tags=["生成批次"])

router.add_api_route("", create_generation_batch, methods=["POST"], response_model=ApiResponse)
router.add_api_route("/{batch_id}", get_generation_batch, methods=["GET"], response_model=ApiResponse)
router.add_api_route("/{batch_id}", update_generation_batch, methods=["PATCH"], response_model=ApiResponse)
router.add_api_route("/{batch_id}/save", save_generation_batch, methods=["POST"], response_model=ApiResponse)

__all__ = [
    "router",
    "VALID_TRANSITIONS",
    "_validate_status_transition",
    "_generate_batch_no",
    "_batch_to_response",
    "_create_case_version_snapshot",
    "_deprecate_case",
    "create_generation_batch",
    "get_generation_batch",
    "update_generation_batch",
    "save_generation_batch",
]
