"""Pipeline 恢复端点与 AI 客户端工厂

提供恢复暂停 Pipeline 的端点，以及创建 AI 客户端的工厂函数。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loguru import logger

from app.ai.client import AIClient
from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.pipeline_schemas import PipelineResumeRequest
from app.api.v1.endpoints.pipeline_deps import verify_iteration_access
from app.core.exception import create_response
from app.schemas.common import ApiResponse

router = APIRouter(tags=["Pipeline管理"])


def create_ai_client(model_name: Optional[str] = None) -> AIClient:
    """创建 AI 客户端实例，支持主模型 + 降级模型。"""
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


@router.post("/{run_id}/resume", response_model=ApiResponse)
async def resume_pipeline(
    run_id: int,
    body: PipelineResumeRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复暂停的 Pipeline。"""
    def _resume(sync_db):
        try:
            from app.services import pipeline_service
            from app.pipelines.runner import PipelineRunner
            from app.pipelines.context import PipelineContext

            run = pipeline_service.get_run(sync_db, run_id)
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

            if run.status != "waiting_for_user":
                raise HTTPException(
                    status_code=400,
                    detail=f"Pipeline 状态 '{run.status}' 不允许恢复",
                )

            verify_iteration_access(sync_db, run.iteration_id, current_user)

            pipeline_service.update_run_status(sync_db, run_id, "running")

            ai_client = create_ai_client(None)

            ctx = PipelineContext(
                db=sync_db,
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

            sync_db.commit()
            sync_db.refresh(run)

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
            sync_db.rollback()
            logger.error("Pipeline 恢复失败: {}", e)
            raise HTTPException(status_code=500, detail="Pipeline 恢复失败")

    return await db.run_sync(_resume)
