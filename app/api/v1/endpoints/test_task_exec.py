"""
测试任务执行与摘要端点模块

本模块定义测试任务的执行控制和摘要查询API端点。

路由前缀: /test_task（由父模块注册）
标签: 测试任务管理

端点概览:
    - POST /{task_id}/run     - 执行测试任务
    - GET  /{task_id}/summary - 获取任务执行摘要

权限要求: 所有端点需要Bearer令牌认证

范式说明（R2-1 阶段三，2026-11-17）:
    - 依赖由异步会话依赖收敛为 get_db（同步 Session）；
    - 原「PrimarySessionLocal() 独立会话 + try/finally close」删除，执行引擎与
      可见性配置统一复用请求级会话（单事务）；
    - 引擎内部为同步 API，仍用 asyncio.to_thread / run_async_coro_in_thread
      释放事件循环。
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.access_deps import require_task_access
from app.core.exception import create_response
from app.db.database import get_db
from app.models.enums import ExecStatus
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.services.visibility_config import VisibilityConfigService
from app.utils.async_sync_bridge import run_async_coro_in_thread

router = APIRouter()


async def _enqueue_test_task(db: Session, task_id: int, task: TestTask) -> dict:
    """R5-1 阶段二：worker 模式下只入队，立即返回 queued。

    Web 进程不再执行任务，执行由独立 `executor` 容器领取（见
    `app/services/execution_dispatcher.py` 与 `scripts/run_executor.py`）。
    """
    from app.services.execution_dispatcher import ExecutionDispatcher

    task_name = task.task_name
    total_count = task.total_count or 0
    dispatcher = ExecutionDispatcher(db)
    try:
        queued = await asyncio.to_thread(dispatcher.enqueue, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return {
        "task": {
            "id": task_id,
            "task_name": task_name,
            "status": queued["status"],
            "status_label": queued["status_label"],
        },
        "summary": {
            "task_id": task_id,
            "status": "queued",
            "progress": 0,
            "total_count": total_count,
            "queued_at": queued["queued_at"],
        },
        "executor_mode": "worker",
    }


@router.post("/{task_id}/run")
async def run_test_task(
    task_id: int,
    task: TestTask = Depends(require_task_access),
    db: Session = Depends(get_db),
):
    """执行测试任务

    任务「存在性 + 归属」校验已由 require_task_access 依赖完成
    （不存在 404、非本人项目 403），并直接注入 task 对象。

    执行位置由 `settings.EXECUTOR_MODE` 决定：
        - `inprocess`（默认）：Web 进程内同步执行，行为与 R5-1 前一致；
        - `worker`：仅入队并返回 `queued`，由独立 executor 领取执行。
    """
    from app.core.config import settings

    if settings.EXECUTOR_MODE == "worker":
        return await _enqueue_test_task(db, task_id, task)

    # 提前提取 project_id，避免 task 对象跨会话访问属性
    project_id = task.project_id

    # TestExecutionEngineV2 / VisibilityConfigService 内部为同步 API，
    # 统一用 to_thread 释放事件循环，会话复用请求级 Session（单事务）
    executor = TestExecutionEngineV2(db)
    try:
        executed_task = await run_async_coro_in_thread(executor.execute_test_task(task_id))
        summary = await asyncio.to_thread(executor.get_task_execution_summary, task_id)

        vis_service = VisibilityConfigService()
        config = await asyncio.to_thread(vis_service.get_project_config, db, project_id)
        hidden_fields = config.hidden_fields or []
        if hidden_fields:
            summary = {k: v for k, v in summary.items() if k not in hidden_fields}

        return {"task": executed_task, "summary": summary}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="执行测试任务失败",
        )


@router.get("/{task_id}/summary")
async def get_task_summary(
    task_id: int,
    task: TestTask = Depends(require_task_access),
    db: Session = Depends(get_db),
):
    """获取任务执行摘要（存在性与归属校验由 require_task_access 完成）"""
    try:
        stmt = select(
            func.count(TestResult.id).label("total"),
            func.sum(case((TestResult.exec_status == ExecStatus.PASSED, 1), else_=0)).label(
                "success"
            ),
            func.sum(case((TestResult.exec_status == ExecStatus.FAILED, 1), else_=0)).label(
                "failed"
            ),
        ).where(TestResult.task_id == task_id)
        stats_result = await asyncio.to_thread(db.execute, stmt)
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
            "progress": getattr(task, "progress", 0),
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
            detail="获取任务摘要失败",
        )
