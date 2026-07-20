"""
测试任务端点辅助模块

本模块包含测试任务端点使用的辅助函数和请求模型，从 test_task.py 拆出以控制单文件行数。

内容:
    - 权限校验函数（sync + async 版本）
    - 请求模型定义（CreateTaskRequest/TaskStartConfig）
"""
from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.models.test_task import TestTask
from app.models.project import Project
from app.models.user import User


def _verify_project_access(
    db, project_id: int, current_user: User
) -> None:
    """sync 版本项目权限校验，供 db.run_sync 调用方使用。"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )


def _verify_task_access(
    db, task: TestTask, current_user: User
) -> None:
    """sync 版本任务权限校验，供 db.run_sync 调用方使用。"""
    project = db.query(Project).filter(
        Project.id == task.project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此任务"
        )


async def _verify_project_access_async(
    db: AsyncSession, project_id: int, current_user: User
) -> None:
    """async 版本的项目权限校验，供 async 端点内联调用。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )


async def _verify_task_access_async(
    db: AsyncSession, task: TestTask, current_user: User
) -> None:
    """async 版本的任务权限校验，供 async 端点内联调用。"""
    result = await db.execute(
        select(Project).where(
            Project.id == task.project_id,
            Project.user_id == current_user.id
        )
    )
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此任务"
        )


# 创建任务请求模型
class CreateTaskRequest(BaseModel):
    project_id: int
    task_name: str
    description: Optional[str] = None
    case_ids: List[int] = Field(default_factory=list)


class TaskStartConfig(BaseModel):
    """任务启动配置模型"""
    execution_mode: Optional[str] = Field("smart", description="执行模式")
    mobile_device_id: Optional[str] = Field(None, description="移动设备ID")
