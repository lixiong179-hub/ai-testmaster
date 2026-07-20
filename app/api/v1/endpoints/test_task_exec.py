"""
测试任务执行与摘要端点模块

本模块定义测试任务的执行控制和摘要查询API端点。

路由前缀: /test_task（由父模块注册）
标签: 测试任务管理

端点概览:
    - POST /{task_id}/run     - 执行测试任务
    - GET  /{task_id}/summary - 获取任务执行摘要

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.enums import ExecStatus
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.services.visibility_config import VisibilityConfigService
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


def _verify_task_access(
    db, task: TestTask, current_user: User
) -> None:
    project = db.query(Project).filter(
        Project.id == task.project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此任务"
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


@router.post("/{task_id}/run")
async def run_test_task(
    task_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """执行测试任务"""
    task_result = await db.execute(
        select(TestTask).where(TestTask.id == task_id)
    )
    task = task_result.scalars().first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试任务不存在"
        )
    await _verify_task_access_async(db, task, current_user)
    # 提前提取 project_id，避免 task 对象跨会话访问属性
    project_id = task.project_id

    # TestExecutionEngineV2 内部使用 sync Session API，需独立 sync 会话
    # 性能优化：将 async service 调用放到独立线程，避免 sync_db.query() 阻塞事件循环
    from app.utils.async_sync_bridge import run_async_coro_in_thread
    sync_db = PrimarySessionLocal()
    try:
        executor = TestExecutionEngineV2(sync_db)
        try:
            executed_task = await run_async_coro_in_thread(
                executor.execute_test_task(task_id)
            )

            # sync 调用（get_task_execution_summary / get_project_config）通过 to_thread 释放事件循环
            summary = await asyncio.to_thread(executor.get_task_execution_summary, task_id)

            vis_service = VisibilityConfigService()
            config = await asyncio.to_thread(
                vis_service.get_project_config, sync_db, project_id
            )
            hidden_fields = config.hidden_fields or []
            if hidden_fields:
                summary = {k: v for k, v in summary.items() if k not in hidden_fields}

            return {
                "task": executed_task,
                "summary": summary
            }
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="执行测试任务失败"
            )
    finally:
        sync_db.close()


@router.get("/{task_id}/summary")
async def get_task_summary(
    task_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务执行摘要"""
    try:
        task_result = await db.execute(
            select(TestTask).where(TestTask.id == task_id)
        )
        task = task_result.scalars().first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        await _verify_task_access_async(db, task, current_user)

        stats_result = await db.execute(
            select(
                func.count(TestResult.id).label('total'),
                func.sum(case((TestResult.exec_status == ExecStatus.PASSED, 1), else_=0)).label('success'),
                func.sum(case((TestResult.exec_status == ExecStatus.FAILED, 1), else_=0)).label('failed'),
            ).where(TestResult.task_id == task_id)
        )
        stats = stats_result.first()

        total = stats.total if stats.total else 0
        success_count = stats.success if stats.success else 0
        fail_count = stats.failed if stats.failed else 0

        summary = {
            "task_id": task_id,
            "task_name": task.task_name,
            "status": task.status,
            "total_count": task.total_count or total,
            "success_count": success_count,
            "fail_count": fail_count,
            "progress": getattr(task, 'progress', 0),
            "start_time": task.start_time.isoformat() if task.start_time else None,
            "end_time": task.end_time.isoformat() if task.end_time else None,
        }
        return create_response(data=summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务摘要失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务摘要失败"
        )
