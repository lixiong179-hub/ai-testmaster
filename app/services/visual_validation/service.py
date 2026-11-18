"""视觉校验接线服务（R3-3）。

接线点：`app/api/v1/endpoints/execution_core` 的失败分析路径，在失败分析
Agent 触发之后，按开关决定是否以 fire-and-forget 方式触发视觉校验管线
`pipeline=["visual_validation"]`。

设计约束（与 R1-1 失败分析一致）：
    - 后台执行：`AgentRuntime.run` 会阻塞，不得在主请求路径 await；
    - 独立会话：请求结束后请求会话失效，后台任务必须使用
      `AsyncPrimarySessionLocal` 新建会话；
    - 异常隔离：任何异常仅 warning，不影响主流程响应；
    - 默认关：全局开关关闭时**不查项目配置、不建会话**（零开销）。
"""

import asyncio
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Project
from app.services.visual_validation.config_service import resolve_enabled


async def is_visual_validation_enabled(db: Any, project_id: int | None) -> bool:
    """判断本次执行是否应触发视觉校验（全局 AND 项目双开关）。

    全局关闭时直接返回 False —— 不产生任何 SQL 查询与会话，保证零开销。

    Args:
        db: 异步会话（AsyncSession）。
        project_id: 项目 ID。

    Returns:
        bool: 是否触发视觉校验。
    """
    if not settings.AI_VISUAL_VALIDATION_ENABLED:
        return False
    if db is None or project_id is None:
        return False
    try:
        result = await db.execute(select(Project.config).where(Project.id == project_id))
        project_config = result.scalar_one_or_none()
    except Exception:
        logger.warning("读取项目级视觉校验配置失败，按关闭处理", exc_info=True)
        return False
    return resolve_enabled(project_config)


def is_visual_validation_enabled_sync(db: Session, project_id: int | None) -> bool:
    """同步版视觉校验开关判断（R2-1 单范式，语义与 async 版完全一致）。

    全局关闭时直接返回 False —— 不产生任何 SQL 查询与会话，保证零开销。
    调用方（同步会话端点）应包在 ``asyncio.to_thread`` 中执行。
    """
    if not settings.AI_VISUAL_VALIDATION_ENABLED:
        return False
    if db is None or project_id is None:
        return False
    try:
        project_config = db.execute(select(Project.config).where(Project.id == project_id)).scalar_one_or_none()
    except Exception:
        logger.warning("读取项目级视觉校验配置失败，按关闭处理", exc_info=True)
        return False
    return resolve_enabled(project_config)


def spawn_visual_validation_agent(
    *,
    project_id: int,
    created_by: int | None = None,
    screenshot_url: str | None = None,
    last_error: str | None = None,
) -> None:
    """fire-and-forget 触发视觉校验 Agent 管线。

    Args:
        project_id: 项目 ID。
        created_by: 触发用户 ID。
        screenshot_url: 待校验截图 URL（注入 ExecutionStateArtifact）。
        last_error: 最近错误信息（注入 ExecutionStateArtifact，供 Agent 判读）。
    """

    async def _run() -> None:
        try:
            from app.db.database import AsyncPrimarySessionLocal
            from app.services.agent.artifacts import ExecutionStateArtifact
            from app.services.agent.orchestrator import AgentOrchestrator
            from app.services.agent.runtime import AgentRuntime
            from app.services.agent.session_service import SessionService

            async with AsyncPrimarySessionLocal() as db:
                orchestrator = AgentOrchestrator(runtime=AgentRuntime(db=db, session_service=SessionService()))
                await orchestrator.execute_pipeline(
                    pipeline=["visual_validation"],
                    project_id=project_id,
                    initial_artifacts=[
                        ExecutionStateArtifact(
                            last_error=last_error,
                            screenshot_url=screenshot_url,
                        )
                    ],
                    created_by=created_by,
                )
                await db.commit()
        except Exception as e:
            # 异常隔离：仅告警，不冒泡到 HTTP 响应
            logger.warning(f"触发视觉校验 Agent 失败（不影响主流程）: {e}")

    asyncio.create_task(_run())


__all__ = ["is_visual_validation_enabled", "spawn_visual_validation_agent"]
