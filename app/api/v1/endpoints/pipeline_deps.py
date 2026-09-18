"""Pipeline 权限校验工具

提供项目与迭代级别的权限校验函数，供各子模块共用。

注（2026-09-18，R0-3 归属校验归一）：
    项目级校验的唯一实现源已统一至 ``app/api/v1/endpoints/access_deps.py``。
    本模块对两个项目级函数**仅做 re-export**，使既有调用方
    （bug.py / pipeline.py / pipeline_precheck.py / mcp_server.py）的
    import 路径保持不变、无需改动。
    迭代级校验（verify_iteration_access / _async）暂留本模块，待后续统一。
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.iteration import Iteration

# 项目级归属校验：唯一实现源在 access_deps，此处 re-export（勿在本模块重复实现）
from app.api.v1.endpoints.access_deps import (
    verify_project_access,
    verify_project_access_async,
)

__all__ = [
    "verify_project_access",
    "verify_project_access_async",
    "verify_iteration_access",
    "verify_iteration_access_async",
]


def verify_iteration_access(
    db: Session, iteration_id: int, current_user: User
) -> Iteration:
    """校验当前用户是否拥有指定迭代的操作权限，返回迭代对象。"""
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


async def verify_iteration_access_async(
    db: AsyncSession, iteration_id: int, current_user: User
) -> Iteration:
    """校验当前用户是否拥有指定迭代的操作权限（async 版本），返回迭代对象。

    语义与 sync 版完全一致，供端点 inline async 调用使用。
    """
    iteration = (
        await db.execute(
            select(Iteration).where(Iteration.id == iteration_id)
        )
    ).scalar_one_or_none()
    if not iteration:
        raise HTTPException(status_code=404, detail="迭代不存在")
    from app.models.project import Project
    project = (
        await db.execute(
            select(Project).where(
                Project.id == iteration.project_id,
                Project.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此迭代的 Pipeline")
    return iteration
