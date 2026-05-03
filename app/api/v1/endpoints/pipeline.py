"""Pipeline 运行管理端点

提供触发 Pipeline 运行、查询运行状态、恢复暂停的 Pipeline 等功能。
"""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.iteration import Iteration
from app.models.pipeline import Artifact
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response

router = APIRouter(prefix="/pipeline", tags=["Pipeline管理"])


class PipelineRunRequest(BaseModel):
    scenario: int = Field(1, ge=1, le=8, description="场景编号")
    ai_model: Optional[str] = Field(None, description="指定 AI 模型（可选）")
    dry_run: bool = Field(False, description="试运行模式")


class PipelineResumeRequest(BaseModel):
    confirmation_payload: Optional[dict] = Field(None, description="确认载荷")


class SupplementSignalsRequest(BaseModel):
    confirmed_capabilities: list[dict] = Field(default_factory=list, description="确认后的业务能力列表")
    answers: list[dict] = Field(default_factory=list, description="对 AI 疑问的回答")
    change_summary: Optional[dict] = Field(None, description="变更摘要（旧项目模式）")
    notes: Optional[str] = Field(None, description="补充说明")


def _verify_iteration_access(
    db: Session, iteration_id: int, current_user: User
) -> Iteration:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if not iteration:
        raise HTTPException(status_code=404, detail="迭代不存在")
    from app.models.project import Project
    project = db.query(Project).filter(
        Project.id == iteration.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此迭代的 Pipeline")
    return iteration


@router.post("/iteration/{iteration_id}/run", response_model=dict)
async def run_pipeline(
    iteration_id: int,
    body: PipelineRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发 Pipeline 运行。"""
    try:
        iteration = _verify_iteration_access(db, iteration_id, current_user)

        if iteration.status not in ("draft", "in_pipeline"):
            raise HTTPException(
                status_code=400,
                detail=f"迭代状态 '{iteration.status}' 不允许启动 Pipeline",
            )

        from app.pipelines.scenarios import get_scenario
        scenario_config = get_scenario(body.scenario)
        if not scenario_config:
            raise HTTPException(status_code=400, detail=f"场景 {body.scenario} 不存在")

        from app.services import pipeline_service
        from app.pipelines.runner import PipelineRunner
        from app.pipelines.context import PipelineContext
        from app.ai.openai_client import OpenAIClient
        from app.ai.fallback_client import FallbackAIClient
        from app.core.config import settings

        input_hash = pipeline_service.compute_input_hash(iteration.inputs)
        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration_id,
            input_hash=input_hash,
            pipeline_version=scenario_config["version"],
        )
        db.flush()

        if iteration.status == "draft":
            from app.services.iteration_service import transition_iteration_status
            transition_iteration_status(db, iteration_id, "in_pipeline")

        ai_client = _create_ai_client(body.ai_model)

        ctx = PipelineContext(
            db=db,
            ai_client=ai_client,
            run=run,
            iteration_id=iteration_id,
            user_id=current_user.id,
            config={"dry_run": body.dry_run},
        )

        runner = PipelineRunner(scenario_config["name"], scenario_config["steps"])
        runner.run(ctx)

        db.commit()
        db.refresh(run)

        return create_response(
            data={
                "run_id": run.id,
                "iteration_id": iteration_id,
                "status": run.status,
                "scenario": body.scenario,
            },
            msg="Pipeline 运行完成",
        )

    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("Pipeline 运行失败: {}", e)
        raise HTTPException(status_code=500, detail=f"Pipeline 运行失败: {str(e)}")


@router.get("/{run_id}", response_model=dict)
async def get_pipeline_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询 Pipeline 运行状态。"""
    try:
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        _verify_iteration_access(db, run.iteration_id, current_user)

        steps_data = []
        for step in run.steps:
            steps_data.append({
                "id": step.id,
                "step_name": step.step_name,
                "status": step.status,
                "started_at": step.started_at,
                "finished_at": step.finished_at,
                "error": step.error,
                "retried_count": step.retried_count,
                "degraded": step.degraded,
            })

        artifacts_data = []
        for artifact in run.artifacts:
            artifacts_data.append({
                "id": artifact.id,
                "kind": artifact.kind,
                "confidence": artifact.confidence,
                "schema_version": artifact.schema_version,
                "created_at": artifact.created_at,
            })

        return create_response(
            data={
                "id": run.id,
                "iteration_id": run.iteration_id,
                "input_hash": run.input_hash,
                "pipeline_version": run.pipeline_version,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "error": run.error,
                "pause_payload": run.pause_payload,
                "steps": steps_data,
                "artifacts": artifacts_data,
            },
            msg="获取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Pipeline 状态失败: {str(e)}")


@router.post("/{run_id}/resume", response_model=dict)
async def resume_pipeline(
    run_id: int,
    body: PipelineResumeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复暂停的 Pipeline。"""
    try:
        from app.services import pipeline_service
        from app.pipelines.runner import PipelineRunner
        from app.pipelines.context import PipelineContext
        from app.ai.openai_client import OpenAIClient
        from app.ai.fallback_client import FallbackAIClient
        from app.core.config import settings

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        if run.status != "waiting_for_user":
            raise HTTPException(
                status_code=400,
                detail=f"Pipeline 状态 '{run.status}' 不允许恢复",
            )

        _verify_iteration_access(db, run.iteration_id, current_user)

        pipeline_service.update_run_status(db, run_id, "running")

        ai_client = _create_ai_client(None)

        ctx = PipelineContext(
            db=db,
            ai_client=ai_client,
            run=run,
            iteration_id=run.iteration_id,
            user_id=current_user.id,
        )

        if body.confirmation_payload:
            ctx.set_confirmation_payload(body.confirmation_payload)

        from app.pipelines.scenarios import get_scenario_by_version
        scenario_config = get_scenario_by_version(run.pipeline_version)
        if not scenario_config:
            raise HTTPException(status_code=500, detail="无法找到对应的 Pipeline 场景配置")

        runner = PipelineRunner(scenario_config["name"], scenario_config["steps"])
        runner.run(ctx)

        db.commit()
        db.refresh(run)

        return create_response(
            data={
                "run_id": run.id,
                "status": run.status,
            },
            msg="Pipeline 已恢复",
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Pipeline 恢复失败: {}", e)
        raise HTTPException(status_code=500, detail=f"Pipeline 恢复失败: {str(e)}")


def _create_ai_client(model_name: Optional[str] = None):
    from app.ai.openai_client import OpenAIClient
    from app.ai.fallback_client import FallbackAIClient
    from app.core.config import settings

    primary = OpenAIClient(
        model=model_name or settings.AI_MODEL_NAME,
        api_key=settings.AI_API_KEY,
        base_url=settings.AI_BASE_URL,
        temperature=settings.AI_TEMPERATURE,
        max_tokens=settings.AI_MAX_TOKENS,
    )

    if settings.AI_FALLBACK_MODEL_NAME:
        fallback = OpenAIClient(
            model=settings.AI_FALLBACK_MODEL_NAME,
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
        )
        return FallbackAIClient(primary=primary, fallback=fallback)

    return primary


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

        _verify_iteration_access(db, run.iteration_id, current_user)

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
                "analysis_summary": payload.get("parsed", {}).get("analysis_summary", ""),
                "uncertain_questions": payload.get("parsed", {}).get("uncertain_questions", []),
                "inferred_capabilities": payload.get("parsed", {}).get("inferred_capabilities", []),
                "change_summary": payload.get("parsed", {}).get("change_summary"),
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
        raise HTTPException(status_code=500, detail=f"获取反推摘要失败: {str(e)}")


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

        _verify_iteration_access(db, run.iteration_id, current_user)

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
        raise HTTPException(status_code=500, detail=f"保存补全信号失败: {str(e)}")
