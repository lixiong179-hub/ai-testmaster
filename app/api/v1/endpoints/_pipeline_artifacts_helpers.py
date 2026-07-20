"""pipeline_artifacts 端点共享常量与工具函数。

包含 payload 截断、取消权限校验、版本重跑指标记录等纯工具逻辑，
供路由处理函数与外部模块复用。
"""
import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, joinedload

from loguru import logger

from app.models.iteration import Iteration
from app.models.pipeline import Artifact, PipelineRun
from app.models.project import Project
from app.models.user import User

PAYLOAD_TRUNCATE_THRESHOLD = 10 * 1024  # 10KB 截断阈值


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


async def _get_run_async(
    db: AsyncSession, run_id: int
) -> Optional[PipelineRun]:
    """async 版本的 pipeline_service.get_run，joinedload steps/artifacts。"""
    result = await db.execute(
        select(PipelineRun)
        .options(
            joinedload(PipelineRun.steps),
            joinedload(PipelineRun.artifacts),
        )
        .where(PipelineRun.id == run_id)
    )
    return result.scalars().first()


async def _verify_iteration_access_async(
    db: AsyncSession, iteration_id: int, current_user: User
) -> Iteration:
    """async 版本的 verify_iteration_access，校验迭代操作权限并返回迭代对象。"""
    iter_result = await db.execute(
        select(Iteration).where(Iteration.id == iteration_id)
    )
    iteration = iter_result.scalars().first()
    if not iteration:
        raise HTTPException(status_code=404, detail="迭代不存在")
    project_result = await db.execute(
        select(Project).where(
            Project.id == iteration.project_id,
            Project.user_id == current_user.id,
        )
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此迭代的 Pipeline")
    return iteration


async def _get_artifact_async(
    db: AsyncSession,
    run_id: int,
    *,
    artifact_id: Optional[int] = None,
    kind: Optional[str] = None,
    order_by_created_desc: bool = False,
) -> Optional[Artifact]:
    """async 版本的 Artifact 查询，支持按 artifact_id 或 kind 过滤。

    Args:
        db: AsyncSession
        run_id: PipelineRun ID
        artifact_id: 可选, 按产物ID过滤
        kind: 可选, 按产物kind过滤
        order_by_created_desc: 是否按 created_at 降序排序

    Returns:
        Optional[Artifact]
    """
    stmt = select(Artifact).where(Artifact.run_id == run_id)
    if artifact_id is not None:
        stmt = stmt.where(Artifact.id == artifact_id)
    if kind is not None:
        stmt = stmt.where(Artifact.kind == kind)
    if order_by_created_desc:
        stmt = stmt.order_by(Artifact.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().first()
