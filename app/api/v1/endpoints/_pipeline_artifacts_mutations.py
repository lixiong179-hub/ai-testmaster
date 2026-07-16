"""pipeline_artifacts 端点写入类路由处理函数。

包含信号补全、取消 Pipeline 运行等 POST/PUT 路由处理函数，
以普通 async 函数形式定义，由 pipeline_artifacts.py 通过
router.add_api_route 注册，保持 router 定义在原文件中。
"""
import hashlib
import json

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.db.database import async_get_db
from app.models.user import User
from app.models.pipeline import Artifact
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_deps import verify_iteration_access
from app.api.v1.endpoints.pipeline_schemas import SupplementSignalsRequest
from app.api.v1.endpoints._pipeline_artifacts_helpers import (
    CANCELLABLE_STATUSES,
    _check_cancel_permission,
)
from app.core.exception import create_response


async def supplement_signals(
    run_id: int,
    body: SupplementSignalsRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """保存用户补全的信号（确认能力 + 回答疑问）"""
    def _supplement(sync_db):
        try:
            from app.services import pipeline_service

            run = pipeline_service.get_run(sync_db, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

            verify_iteration_access(sync_db, run.iteration_id, current_user)

            has_changes = (
                len(body.confirmed_capabilities) > 0
                or len(body.answers) > 0
                or body.change_summary is not None
            )
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

            existing = (
                sync_db.query(Artifact)
                .filter(
                    Artifact.run_id == run_id,
                    Artifact.kind == "supplemented_signals",
                )
                .first()
            )

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
                sync_db.add(supplement_artifact)

            sync_db.commit()

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
            sync_db.rollback()
            logger.error("保存补全信号失败: %s", e)
            raise HTTPException(status_code=500, detail="保存补全信号失败")

    return await db.run_sync(_supplement)


async def cancel_pipeline_run(
    run_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """取消 Pipeline 运行。

    仅 running / waiting_for_user / pending 状态的运行可取消。
    取消后 Runner 在下一个 Step 边界检测到 cancelled 状态即停止执行。
    """
    def _cancel(sync_db):
        try:
            from app.services import pipeline_service

            run = pipeline_service.get_run(sync_db, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

            verify_iteration_access(sync_db, run.iteration_id, current_user)

            if run.status not in CANCELLABLE_STATUSES:
                raise HTTPException(
                    status_code=409,
                    detail=f"当前状态 '{run.status}' 不允许取消，仅 {sorted(CANCELLABLE_STATUSES)} 状态可取消",
                )

            _check_cancel_permission(sync_db, run, current_user)

            from_status = run.status

            try:
                pipeline_service.update_run_status(
                    db=sync_db, run_id=run_id, status="cancelled",
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
                    iteration_id=run.iteration_id,
                )
            except Exception as audit_err:
                logger.warning("审计日志写入失败(不影响取消操作): %s", audit_err)

            sync_db.commit()
            sync_db.refresh(run)

            return create_response(
                data={
                    "run_id": run.id,
                    "status": run.status,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                },
                msg="Pipeline 运行已取消",
            )

        except HTTPException:
            raise
        except Exception as e:
            sync_db.rollback()
            logger.error("取消 Pipeline 运行失败: %s", e)
            raise HTTPException(status_code=500, detail="取消 Pipeline 运行失败")

    return await db.run_sync(_cancel)
