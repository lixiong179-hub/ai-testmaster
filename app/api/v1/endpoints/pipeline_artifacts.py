"""Pipeline 反推摘要与信号补充端点

提供获取 AI 反推业务摘要、保存用户补全信号的功能，以及版本重跑指标记录。
"""
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.pipeline import Artifact
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_schemas import SupplementSignalsRequest
from app.api.v1.endpoints.pipeline_deps import verify_iteration_access
from app.core.exception import create_response

router = APIRouter(tags=["Pipeline管理"])


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
        logger.error("获取Pipeline摘要失败: {}", e)
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
        logger.error("获取反推摘要失败: {}", e)
        raise HTTPException(status_code=500, detail="获取反推摘要失败")


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
        logger.error("保存补全信号失败: {}", e)
        raise HTTPException(status_code=500, detail="保存补全信号失败")


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
        logger.debug(f"记录pipeline版本重跑指标失败(不影响业务): {e}")
