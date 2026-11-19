"""Pipeline 反推摘要、信号补充、产物详情与取消运行端点

提供获取 AI 反推业务摘要、保存用户补全信号、按 artifact_id 查询产物详情、
取消 Pipeline 运行，以及版本重跑指标记录。

路由处理函数直接内联在本文件中；纯工具函数下沉至：
    - app/services/pipeline_artifacts_helpers.py   常量与纯工具函数

公开符号通过本文件 re-export，保持 import 路径不变。
"""

import asyncio
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_schemas import SupplementSignalsRequest
from app.core.exception import create_response
from app.db.database import PrimarySessionLocal, get_db
from app.models.pipeline import Artifact
from app.models.user import User
from app.api.v1.endpoints.access_deps import (
    verify_iteration_access as _verify_iteration_access,
)
from app.schemas.common import ApiResponse
from app.services.pipeline_artifacts_helpers import (
    CANCELLABLE_STATUSES,
    PAYLOAD_TRUNCATE_THRESHOLD,
    _check_cancel_permission,
    _truncate_payload,
    record_version_rerun_metric,
    _get_run_async,
    _get_artifact_async,
)

router = APIRouter(tags=["Pipeline管理"])


#: 摘要统计的固定动作键（缺失时保持 0，顺序即响应字段顺序）。
_SUMMARY_ACTION_KEYS = (
    "keep",
    "needs_modify",
    "locator_broken",
    "locator_and_modify",
    "deprecate",
    "add_new",
    "conflict",
    "pending_review",
)


def _resolve_scenario_id(pipeline_version: str | None) -> int:
    """按 pipeline_version 反查场景编号；无匹配返回 0。"""
    from app.pipelines.scenarios import get_scenario_by_version, list_scenarios

    if not get_scenario_by_version(pipeline_version):
        return 0
    for sid, cfg in list_scenarios().items():
        if cfg["version"] == pipeline_version:
            return sid
    return 0


def _aggregate_artifacts(artifacts) -> tuple[dict[str, int], list[int], list[str]]:
    """汇总 run 产物中的动作统计、已持久化用例 ID 与产物种类。"""
    actions = dict.fromkeys(_SUMMARY_ACTION_KEYS, 0)
    persisted_case_ids: list[int] = []
    artifact_kinds: list[str] = []

    for artifact in artifacts:
        artifact_kinds.append(artifact.kind)
        payload = artifact.payload
        if artifact.kind == "merged_verdicts" and payload:
            stats = payload.get("stats", {})
            for key in actions:
                if key in stats:
                    actions[key] = stats[key]
        if artifact.kind == "persisted_case_ids" and payload:
            persisted_case_ids = payload.get("persisted_case_ids", [])

    return actions, persisted_case_ids, sorted(set(artifact_kinds))


async def get_pipeline_summary(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run = await _get_run_async(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        await asyncio.to_thread(_verify_iteration_access, db, run.iteration_id, current_user)

        scenario_id = _resolve_scenario_id(run.pipeline_version)
        actions, persisted_case_ids, artifact_kinds = _aggregate_artifacts(run.artifacts)

        return create_response(
            data={
                "run_id": run.id,
                "status": run.status,
                "scenario": scenario_id,
                "actions": actions,
                "persisted_case_ids": persisted_case_ids,
                "artifact_kinds": artifact_kinds,
            },
            msg="获取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取Pipeline摘要失败: %s", e)
        raise HTTPException(status_code=500, detail="获取Pipeline摘要失败")


async def get_inferred_summary(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 反推的业务摘要（供用户确认/补全）"""
    try:
        run = await _get_run_async(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        await asyncio.to_thread(_verify_iteration_access, db, run.iteration_id, current_user)

        artifact = await _get_artifact_async(
            db,
            run_id,
            kind="inferred_business_summary",
            order_by_created_desc=True,
        )

        if not artifact:
            raise HTTPException(
                status_code=404,
                detail="未找到业务反推摘要，请先运行包含反推步骤的 Pipeline",
            )

        payload = artifact.payload or {}

        return create_response(
            data={
                "artifact_id": artifact.id,
                "kind": artifact.kind,
                "confidence": artifact.confidence,
                "is_old_project": payload.get("is_old_project", False),
                "mode": payload.get("mode", "new_project"),
                "parsed": payload.get("parsed", {}),
                "analysis_summary": (payload.get("parsed") or {}).get("analysis_summary", ""),
                "uncertain_questions": (payload.get("parsed") or {}).get("uncertain_questions", []),
                "inferred_capabilities": (payload.get("parsed") or {}).get("inferred_capabilities", []),
                "change_summary": (payload.get("parsed") or {}).get("change_summary"),
                "needs_confirmation": payload.get("confidence", 1.0) < 0.7,
                "provenance": artifact.provenance or {},
                "run_status": run.status,
            },
            msg="获取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取反推摘要失败: %s", e)
        raise HTTPException(status_code=500, detail="获取反推摘要失败")


async def get_artifact_detail(
    run_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按 artifact_id 查询产物完整 payload。

    大 payload（超过 10KB）自动截断并标记 truncated=true，
    前端可据此提示用户数据不完整。
    """
    try:
        run = await _get_run_async(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        await asyncio.to_thread(_verify_iteration_access, db, run.iteration_id, current_user)

        artifact = await _get_artifact_async(
            db,
            run_id,
            artifact_id=artifact_id,
        )
        if not artifact:
            raise HTTPException(status_code=404, detail="产物不存在或不属于该运行")

        payload, truncated, truncated_reason = _truncate_payload(artifact.payload)

        return create_response(
            data={
                "artifact_id": artifact.id,
                "run_id": artifact.run_id,
                "kind": artifact.kind,
                "schema_version": artifact.schema_version,
                "payload": payload,
                "confidence": artifact.confidence,
                "provenance": artifact.provenance or {},
                "content_hash": artifact.content_hash,
                "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                "truncated": truncated,
                "truncated_reason": truncated_reason,
            },
            msg="获取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取产物详情失败: %s", e)
        raise HTTPException(status_code=500, detail="获取产物详情失败")


async def supplement_signals(
    run_id: int,
    body: SupplementSignalsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存用户补全的信号（确认能力 + 回答疑问）"""
    try:
        run = await _get_run_async(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        await asyncio.to_thread(_verify_iteration_access, db, run.iteration_id, current_user)

        has_changes = len(body.confirmed_capabilities) > 0 or len(body.answers) > 0 or body.change_summary is not None
        if not has_changes:
            raise HTTPException(status_code=400, detail="至少需要提供确认能力、回答或变更摘要中的一项")

        supplement_payload = {
            "iteration_id": run.iteration_id,
            "run_id": run_id,
            "confirmed_capabilities": body.confirmed_capabilities,
            "answers": body.answers,
            "change_summary": body.change_summary,
            "notes": body.notes,
            "supplemented_by": current_user.id,
        }
        raw = json.dumps(supplement_payload, sort_keys=True, ensure_ascii=False, default=str)
        content_hash = hashlib.sha256(raw.encode()).hexdigest()

        # 查询现有 Artifact
        existing_result = await asyncio.to_thread(
            db.execute,
            select(Artifact).where(
                Artifact.run_id == run_id,
                Artifact.kind == "supplemented_signals",
            ),
        )
        existing = existing_result.scalars().first()

        if existing:
            existing.payload = supplement_payload
            existing.content_hash = content_hash
            existing.schema_version = "1.0"
        else:
            supplement_artifact = Artifact(
                run_id=run_id,
                kind="supplemented_signals",
                schema_version="1.0",
                payload=supplement_payload,
                content_hash=content_hash,
                confidence=1.0,
                provenance={
                    "step": "human_supplement",
                    "user_id": current_user.id,
                },
            )
            db.add(supplement_artifact)

        await asyncio.to_thread(db.commit)

        return create_response(
            data={
                "run_id": run_id,
                "capability_count": len(body.confirmed_capabilities),
                "answer_count": len(body.answers),
                "has_change_summary": body.change_summary is not None,
            },
            msg="信号补全已保存",
        )
    except HTTPException:
        raise
    except Exception as e:
        await asyncio.to_thread(db.rollback)
        logger.error("保存补全信号失败: %s", e)
        raise HTTPException(status_code=500, detail="保存补全信号失败")


async def cancel_pipeline_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消 Pipeline 运行。

    仅 running / waiting_for_user / pending 状态的运行可取消。
    取消后 Runner 在下一个 Step 边界检测到 cancelled 状态即停止执行。
    """
    try:
        run = await _get_run_async(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        await asyncio.to_thread(_verify_iteration_access, db, run.iteration_id, current_user)

        if run.status not in CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"当前状态 '{run.status}' 不允许取消，仅 {sorted(CANCELLABLE_STATUSES)} 状态可取消",
            )

        from_status = run.status
        iteration_id = run.iteration_id

        # _check_cancel_permission + pipeline_service.update_run_status + audit_service.log_action 都是 sync 调用，
        # 使用独立 sync 会话 + to_thread 释放事件循环
        def _do_cancel(sync_db):
            # 重新查询 run（不同会话）
            from app.services import pipeline_service

            run_sync = pipeline_service.get_run(sync_db, run_id)
            if not run_sync:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")
            _check_cancel_permission(sync_db, run_sync, current_user)
            try:
                pipeline_service.update_run_status(
                    db=sync_db,
                    run_id=run_id,
                    status="cancelled",
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))

            try:
                from app.services.audit_service import log_action

                log_action(
                    db=sync_db,
                    action="pipeline_cancel",
                    actor_id=current_user.id,
                    target_kind="pipeline_run",
                    target_id=run_id,
                    detail={"from_status": from_status, "to_status": "cancelled"},
                    run_id=run_id,
                    iteration_id=iteration_id,
                )
            except Exception as audit_err:
                logger.warning("审计日志写入失败(不影响取消操作): %s", audit_err)

            sync_db.commit()
            sync_db.refresh(run_sync)
            return run_sync

        sync_db = PrimarySessionLocal()
        try:
            run_sync = await asyncio.to_thread(_do_cancel, sync_db)
        finally:
            sync_db.close()

        return create_response(
            data={
                "run_id": run_sync.id,
                "status": run_sync.status,
                "finished_at": run_sync.finished_at.isoformat() if run_sync.finished_at else None,
            },
            msg="Pipeline 运行已取消",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("取消 Pipeline 运行失败: %s", e)
        raise HTTPException(status_code=500, detail="取消 Pipeline 运行失败")


router.add_api_route("/{run_id}/summary", get_pipeline_summary, methods=["GET"], response_model=ApiResponse)
router.add_api_route("/{run_id}/inferred-summary", get_inferred_summary, methods=["GET"], response_model=ApiResponse)
router.add_api_route(
    "/{run_id}/artifacts/{artifact_id}", get_artifact_detail, methods=["GET"], response_model=ApiResponse
)
router.add_api_route("/{run_id}/supplement-signals", supplement_signals, methods=["PUT"], response_model=ApiResponse)
router.add_api_route("/{run_id}/cancel", cancel_pipeline_run, methods=["POST"], response_model=ApiResponse)

__all__ = [
    "router",
    "CANCELLABLE_STATUSES",
    "PAYLOAD_TRUNCATE_THRESHOLD",
    "_check_cancel_permission",
    "_truncate_payload",
    "record_version_rerun_metric",
    "get_artifact_detail",
    "get_inferred_summary",
    "get_pipeline_summary",
    "cancel_pipeline_run",
    "supplement_signals",
]
