"""pipeline_artifacts 端点查询类路由处理函数。

包含 Pipeline 摘要、AI 反推摘要、产物详情等 GET 路由处理函数，
以普通 async 函数形式定义，由 pipeline_artifacts.py 通过
router.add_api_route 注册，保持 router 定义在原文件中。
"""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.db.database import async_get_db
from app.models.user import User
from app.models.pipeline import Artifact
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_deps import verify_iteration_access
from app.api.v1.endpoints._pipeline_artifacts_helpers import _truncate_payload
from app.core.exception import create_response


async def get_pipeline_summary(
    run_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get_summary(sync_db):
        try:
            from app.services import pipeline_service

            run = pipeline_service.get_run(sync_db, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

            verify_iteration_access(sync_db, run.iteration_id, current_user)

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

    return await db.run_sync(_get_summary)


async def get_inferred_summary(
    run_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 AI 反推的业务摘要（供用户确认/补全）"""
    def _get_inferred(sync_db):
        try:
            from app.services import pipeline_service

            run = pipeline_service.get_run(sync_db, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

            verify_iteration_access(sync_db, run.iteration_id, current_user)

            artifact = (
                sync_db.query(Artifact)
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

    return await db.run_sync(_get_inferred)


async def get_artifact_detail(
    run_id: int,
    artifact_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """按 artifact_id 查询产物完整 payload。

    大 payload（超过 10KB）自动截断并标记 truncated=true，
    前端可据此提示用户数据不完整。
    """
    def _get_detail(sync_db):
        try:
            from app.services import pipeline_service

            run = pipeline_service.get_run(sync_db, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

            verify_iteration_access(sync_db, run.iteration_id, current_user)

            artifact = (
                sync_db.query(Artifact)
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

    return await db.run_sync(_get_detail)
