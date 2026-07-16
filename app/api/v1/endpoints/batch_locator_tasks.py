"""
批量定位器报告与任务管理端点模块

本模块定义批量定位器的报告获取、任务取消和任务列表API端点。

路由前缀: /batch-locator（由父模块注册）
标签: 批量定位器

端点概览:
    - GET  /batch-record-report/{task_id}  - 获取批量定位报告
    - POST /batch-record-cancel/{task_id}  - 取消批量定位任务
    - GET  /batch-tasks                    - 获取批量定位任务列表

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.batch_locator_service import BatchLocatorService
from app.core.exception import create_response

router = APIRouter()


@router.get("/batch-record-report/{task_id}")
async def get_batch_record_report(
    task_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取批量定位报告"""
    service = BatchLocatorService(db)
    report = await service.get_batch_report(task_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    return create_response(data=report)


@router.post("/batch-record-cancel/{task_id}")
async def cancel_batch_record(
    task_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """取消批量定位任务"""
    service = BatchLocatorService(db)
    success = await service.cancel_batch_task(task_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或已完成"
        )

    return create_response(msg="任务已取消")


@router.get("/batch-tasks")
async def get_batch_tasks(
    project_id: int = Query(None, description="项目ID"),
    status_filter: str = Query(None, description="状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取批量定位任务列表"""
    service = BatchLocatorService(db)
    tasks = await service.get_batch_tasks(
        project_id=project_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size
    )

    return create_response(data=tasks)
