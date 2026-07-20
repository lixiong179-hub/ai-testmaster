from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.test_task import TestTask
from app.models.user import User
from app.services.visibility_config import VisibilityConfigService
from app.api.v1.endpoints.auth import get_current_user


class SpeedReplayRequest(BaseModel):
    speed: float = Field(1.0, description="播放速度倍率")


def _filter_by_visibility(data: dict, hidden_fields: list) -> dict:
    if not hidden_fields:
        return data
    return {k: v for k, v in data.items() if k not in hidden_fields}


def _get_hidden_fields(db: Session, project_id: int) -> list:
    vis_service = VisibilityConfigService()
    config = vis_service.get_project_config(db, project_id)
    return config.hidden_fields or []


def verify_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


async def verify_project_permission_async(
    db: AsyncSession, project_id: int, user_id: int
) -> Project:
    """异步版项目权限校验，语义与 sync 版完全一致。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


def get_task_or_404(db: Session, task_id: int, project_id: int) -> TestTask:
    task = db.query(TestTask).filter(
        TestTask.id == task_id,
        TestTask.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    return task
