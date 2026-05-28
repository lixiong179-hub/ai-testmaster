"""Pipeline 反推摘要、信号补充、产物详情与取消运行端点

提供获取 AI 反推业务摘要、保存用户补全信号、按 artifact_id 查询产物详情、
取消 Pipeline 运行，以及版本重跑指标记录。
"""
import hashlib
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.pipeline import Artifact, PipelineRun
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_schemas import SupplementSignalsRequest
from app.api.v1.endpoints.pipeline_deps import verify_iteration_access
from app.core.exception import create_response

router = APIRouter(tags=["Pipeline管理"])

PAYLOAD_TRUNCATE_THRESHOLD = 10 * 1024  # 10KB 截断阈值


@router.get("/{run_id}/summary", response_model=dict)
async def get_pipeline_summary(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        verify_iteration_access(db, run.iteration_id, current_user)

        from app.pipelines.scenarios import get_scenario_by_version
        scenario_config = get_scenario_by_version(run.pipeline_version)
        scenario_id = 0
        if scenario_config:
            from app.pipelines.scenarios import list_scenarios
            for sid, cfg in list_scenarios().items():
                if cfg["version"] == run.pipeline_version:
                    scenario_id = sid
                    break

        actions = {
            "keep": 0, "needs_modify": 0, "locator_broken": 0,
            "locator_and_modify": 0, "deprecate": 0, "add_new": 0,
            "conflict": 0, "pending_review": 0,
        }
        persisted_case_ids: list[int] = []
        artifact_kinds: list[str] = []

        for artifact in run.artifacts:
            artifact_kinds.append(artifact.kind)
            if artifact.kind == "merged_verdicts" and artifact.payload:
                stats = artifact.payload.get("stats", {})
                for key in actions:
                    if key in stats:
                        actions[key] = stats[key]
            if artifact.kind == "persisted_case_ids" and artifact.payload:
                persisted_case_ids = artifact.payload.get("persisted_case_ids", [])

        artifact_kinds = sorted(set(artifact_kinds))

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


@router.get("/{run_id}/inferred-summary", response_model=dict)
async def get_inferred_summary(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 反推的业务摘要（供用户确认/补全）"""
    try:
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        verify_iteration_access(db, run.iteration_id, current_user)

        artifact = (
            db.query(Artifact)
            .filter(
                Artifact.run_id == run_id,
                Artifact.kind == "inferred_business_summary",
            )
            .order_by(Artifact.created_at.desc())
            .first()
        )

        if not artifact:
            raise HTTPException(status_code=404, detail="未找到业务反推摘要，请先运行包含反推步骤的 Pipeline")

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


def _truncate_payload(payload: Any) -> tuple[Any, bool, Optional[str]]:
    """截断大 payload，超过阈值时仅保留前 N 条并标记截断。

    Args:
        payload: 原始 payload 数据。

    Returns:
        (截断后的 payload, 是否截断, 截断原因)
    """
    raw_size = len(json.dumps(payload, default=str).encode("utf-8"))
    if raw_size <= PAYLOAD_TRUNCATE_THRESHOLD:
        return payload, False, None

    if isinstance(payload, list):
        max_items = 50
        truncated = payload[:max_items]
        reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，仅展示前 {max_items} 条"
        return truncated, True, reason

    if isinstance(payload, dict):
        max_keys = 50
        truncated = dict(list(payload.items())[:max_keys])
        reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，仅展示前 {max_keys} 个键"
        return truncated, True, reason

    if isinstance(payload, str):
        max_chars = PAYLOAD_TRUNCATE_THRESHOLD
        truncated = payload[:max_chars]
        reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，仅展示前 {max_chars} 字符"
        return truncated, True, reason

    reason = f"payload 大小 {raw_size} 字节超过 {PAYLOAD_TRUNCATE_THRESHOLD} 字节阈值，类型不可截断"
    return None, True, reason


@router.get("/{run_id}/artifacts/{artifact_id}", response_model=dict)
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
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        verify_iteration_access(db, run.iteration_id, current_user)

        artifact = (
            db.query(Artifact)
            .filter(Artifact.id == artifact_id, Artifact.run_id == run_id)
            .first()
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


@router.put("/{run_id}/supplement-signals", response_model=dict)
async def supplement_signals(
    run_id: int,
    body: SupplementSignalsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存用户补全的信号（确认能力 + 回答疑问）"""
    try:
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        verify_iteration_access(db, run.iteration_id, current_user)

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
            db.query(Artifact)
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
            db.add(supplement_artifact)

        db.commit()

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
        db.rollback()
        logger.error("保存补全信号失败: %s", e)
        raise HTTPException(status_code=500, detail="保存补全信号失败")


CANCELLABLE_STATUSES = {"running", "waiting_for_user", "pending"}


def _check_cancel_permission(
    db: Session, run: PipelineRun, current_user: User,
) -> None:
    """校验当前用户是否有权取消指定 Pipeline 运行。

    权限规则：
        - admin 拥有 pipeline:cancel:all，可取消任意运行。
        - qa_lead 拥有 pipeline:cancel:own，仅可取消自己发起的运行。
        - 其他角色无 cancel 权限，返回 403。

    Args:
        db: 数据库会话。
        run: PipelineRun 记录。
        current_user: 当前登录用户。

    Raises:
        HTTPException: 403 无权限。
    """
    from app.services.pipeline_permission_service import check_pipeline_permission
    from app.models.iteration import Iteration

    iteration = db.query(Iteration).filter(Iteration.id == run.iteration_id).first()
    project_id = iteration.project_id if iteration else None

    if check_pipeline_permission(
        db, current_user.id, "pipeline", "cancel", "own", project_id=project_id,
    ):
        has_all_scope = check_pipeline_permission(
            db, current_user.id, "pipeline", "cancel", "all", project_id=project_id,
        )
        if has_all_scope:
            return
        if run.triggered_by == current_user.id:
            return
        raise HTTPException(status_code=403, detail="仅可取消自己发起的 Pipeline 运行")
    raise HTTPException(status_code=403, detail="缺少 pipeline:cancel 权限")


@router.post("/{run_id}/cancel", response_model=dict)
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
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        verify_iteration_access(db, run.iteration_id, current_user)

        if run.status not in CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"当前状态 '{run.status}' 不允许取消，仅 {sorted(CANCELLABLE_STATUSES)} 状态可取消",
            )

        _check_cancel_permission(db, run, current_user)

        from_status = run.status

        try:
            pipeline_service.update_run_status(
                db=db, run_id=run_id, status="cancelled",
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        try:
            from app.services.audit_service import log_action
            log_action(
                db=db,
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

        db.commit()
        db.refresh(run)

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
        db.rollback()
        logger.error("取消 Pipeline 运行失败: %s", e)
        raise HTTPException(status_code=500, detail="取消 Pipeline 运行失败")


def record_version_rerun_metric(
    db: Session,
    iteration_id: Optional[int] = None,
    detail: Optional[dict] = None,
) -> None:
    """记录 F14 Pipeline 版本升级强制重跑指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        record_metric(
            "pipeline_version_rerun",
            iteration_id=iteration_id,
            detail=detail,
        )
    except Exception as e:
        logger.debug("记录pipeline版本重跑指标失败(不影响业务): %s", e)
