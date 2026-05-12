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
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


def _verify_task_access(
    db: Session, task: TestTask, current_user: User
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


@router.post("/{task_id}/run")
async def run_test_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """执行测试任务"""
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试任务不存在"
        )

    _verify_task_access(db, task, current_user)

    # 创建测试执行器
    executor = TestExecutionEngineV2(db)

    # 执行测试任务
    try:
        executed_task = await executor.execute_test_task(task_id)

        # 获取执行摘要
        summary = executor.get_task_execution_summary(task_id)

        return {
            "task": executed_task,
            "summary": summary
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="执行测试任务失败"
        )


@router.get("/{task_id}/summary")
async def get_task_summary(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取任务执行摘要"""
    try:
        from sqlalchemy import case, func

        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        _verify_task_access(db, task, current_user)

        stats = db.query(
            func.count(TestResult.id).label('total'),
            func.sum(case((TestResult.exec_status == 1, 1), else_=0)).label('success'),
            func.sum(case((TestResult.exec_status == 2, 1), else_=0)).label('failed'),
        ).filter(TestResult.task_id == task_id).first()

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
