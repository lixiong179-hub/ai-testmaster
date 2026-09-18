"""
测试任务端点模块

本模块定义测试任务的API端点，用于管理测试执行任务的创建、查询和状态控制。

路由前缀: /test-task
标签: 测试任务管理

端点概览:
    - POST  /                     - 创建测试任务
    - GET   /                     - 获取任务列表
    - GET   /{task_id}            - 获取任务详情
    - POST  /{task_id}/start      - 开始执行测试任务
    - DELETE /{task_id}           - 删除任务

子模块:
    - test_task_exec: 执行控制和摘要查询

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, insert, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.utils.db_time import utcnow
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.enums import ExecStatus
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.services.visibility_config import VisibilityConfigService
from app.core.exception import create_response
from app.schemas.common import ApiResponse
from loguru import logger

from app.api.v1.endpoints.test_task_helpers import (
    CreateTaskRequest,
    TaskStartConfig,
)
from app.api.v1.endpoints.access_deps import (
    require_task_access,
    verify_project_access_async,
)
from app.api.v1.endpoints.test_task_exec import router as exec_router

router = APIRouter(prefix="/test-task", tags=["测试任务管理"])

# 注册子模块路由
router.include_router(exec_router)

# Task E-06: 执行队列排序白名单。
# 将前端传入的 sort_by 字符串映射到 TestTask 列对象，既实现字段白名单校验
# （防 SQL 注入：非白名单字段直接拒绝），又避免 getattr 动态取列的隐式风险。
TASK_SORT_FIELD_MAP = {
    "create_time": TestTask.create_time,
    "status": TestTask.status,
    "priority": TestTask.priority,
    "start_time": TestTask.start_time,
    "end_time": TestTask.end_time,
}


@router.post("/", response_model=ApiResponse)
async def create_test_task(
    request_data: CreateTaskRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """创建测试任务"""
    try:
        project_id = request_data.project_id
        task_name = request_data.task_name
        test_case_ids = request_data.case_ids

        await verify_project_access_async(db, project_id, current_user)
        new_task = TestTask(
            project_id=project_id,
            task_name=task_name,
            case_ids=test_case_ids or [],
            executor_id=current_user.id,
            status=0,
            total_count=len(test_case_ids) if test_case_ids else 0
        )
        db.add(new_task)
        await db.flush()

        if test_case_ids:
            cases_result = await db.execute(
                select(TestCase).where(
                    TestCase.id.in_(test_case_ids),
                    TestCase.project_id == project_id,
                    TestCase.is_deleted.is_(False)
                )
            )
            test_cases = cases_result.scalars().all()
            case_map = {tc.id: tc for tc in test_cases}
            task_results_to_insert = []
            for case_id in test_case_ids:
                test_case = case_map.get(case_id)
                if test_case:
                    task_results_to_insert.append({
                        "task_id": new_task.id,
                        "project_id": project_id,
                        "case_id": case_id,
                        "case_no": test_case.case_no,
                        "exec_status": ExecStatus.NOT_EXECUTED
                    })
            if task_results_to_insert:
                await db.execute(insert(TestResult), task_results_to_insert)

        await db.commit()
        await db.refresh(new_task)
        data = {
            "task_id": new_task.id,
            "task_name": new_task.task_name,
            "project_id": new_task.project_id,
            "total_count": new_task.total_count,
            "create_time": new_task.create_time
        }
        return create_response(data=data)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"创建测试任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建测试任务失败"
        )


@router.get("/", response_model=ApiResponse)
async def get_test_tasks(
    project_id: Optional[int] = Query(None, description="项目ID"),
    task_status: Optional[int] = Query(None, description="任务状态"),
    sort_by: str = Query("create_time", description="排序字段: create_time/status/priority/start_time/end_time"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试任务列表

    Task E-06: 支持按 create_time/status/priority/start_time/end_time 排序，
    排序字段经白名单（TASK_SORT_FIELD_MAP）校验，非白名单值返回 400，
    避免 SQL 注入风险。无排序参数时默认 create_time desc。
    """
    # 白名单校验：防 SQL 注入，非白名单字段直接拒绝
    if sort_by not in TASK_SORT_FIELD_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的排序字段: {sort_by}"
        )
    if sort_order not in ("asc", "desc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="排序方向仅支持 asc/desc"
        )
    if project_id is not None:
        await verify_project_access_async(db, project_id, current_user)
        base_query = select(TestTask).where(TestTask.project_id == project_id)
        count_query = select(func.count()).select_from(TestTask).where(TestTask.project_id == project_id)
    else:
        base_query = select(TestTask).join(
            Project,
            Project.id == TestTask.project_id
        ).where(Project.user_id == current_user.id)
        count_query = select(func.count()).select_from(TestTask).join(
            Project,
            Project.id == TestTask.project_id
        ).where(Project.user_id == current_user.id)
    if task_status is not None:
        base_query = base_query.where(TestTask.status == task_status)
        count_query = count_query.where(TestTask.status == task_status)
    # 动态排序：主排序字段 + id 兜底，保证分页稳定（同值时按 id desc 决定顺序）
    sort_column = TASK_SORT_FIELD_MAP[sort_by]
    order_clause = asc(sort_column) if sort_order == "asc" else desc(sort_column)
    base_query = base_query.order_by(order_clause, TestTask.id.desc())
    offset = (page - 1) * page_size
    tasks_result = await db.execute(
        base_query.offset(offset).limit(page_size)
    )
    test_tasks = tasks_result.scalars().all()
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    items = []
    for task in test_tasks:
        items.append({
            "id": task.id,
            "task_name": task.task_name,
            "project_id": task.project_id,
            "case_ids": task.case_ids or [],
            "executor_id": task.executor_id,
            "status": task.status,
            "priority": getattr(task, 'priority', 2),
            "total_count": task.total_count,
            "success_count": getattr(task, 'success_count', 0),
            "fail_count": getattr(task, 'fail_count', 0),
            "progress": getattr(task, 'progress', 0),
            "start_time": getattr(task, 'start_time', None),
            "end_time": getattr(task, 'end_time', None),
            "create_time": task.create_time,
            "update_time": getattr(task, 'update_time', None)
        })
    data = {"total": total, "items": items}
    return create_response(data=data)


@router.get("/{task_id}", response_model=ApiResponse)
async def get_test_task(
    task_id: int,
    task: TestTask = Depends(require_task_access),
    db: AsyncSession = Depends(async_get_db)
):
    """获取测试任务详情（存在性与归属校验由 require_task_access 完成）"""
    try:
        # 提前提取 project_id，避免 task 对象跨会话属性访问
        project_id = task.project_id

        results_result = await db.execute(
            select(TestResult).where(TestResult.task_id == task_id)
        )
        task_results = results_result.scalars().all()

        # VisibilityConfigService 是 sync service，使用 PrimarySessionLocal 通过 to_thread 释放事件循环
        import asyncio
        vis_service = VisibilityConfigService()
        sync_db = PrimarySessionLocal()
        try:
            vis_config = await asyncio.to_thread(
                vis_service.get_project_config, sync_db, project_id
            )
        finally:
            sync_db.close()
        hidden_fields = vis_config.hidden_fields or []
        results_data = []
        for tr in task_results:
            tr_dict = {
                "id": tr.id,
                "task_id": tr.task_id,
                "case_id": tr.case_id,
                "case_no": getattr(tr, 'case_no', None),
                "exec_status": tr.exec_status,
                "exec_time": tr.exec_time,
                "error_msg": getattr(tr, 'error_msg', None),
                "exec_log": getattr(tr, 'exec_log', None),
            }
            if hidden_fields:
                tr_dict = {k: v for k, v in tr_dict.items() if k not in hidden_fields}
            results_data.append(tr_dict)
        return {"task": task, "results": results_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测试任务详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取测试任务详情失败"
        )


@router.post("/{task_id}/start", response_model=ApiResponse)
async def start_test_task(
    task_id: int,
    task: TestTask = Depends(require_task_access),
    config: Optional[TaskStartConfig] = None,
    db: AsyncSession = Depends(async_get_db)
):
    """开始执行测试任务（支持执行模式和设备参数）

    存在性与归属校验由 require_task_access 完成。
    """
    try:
        # 允许从 WAITING(0)/FAILED(3)/STOPPED(4) 启动或重试
        if task.status not in [0, 3, 4]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务状态不允许开始执行 (当前状态: {task.status})"
            )

        execution_mode = "smart"
        mobile_device_id = None
        if config:
            execution_mode = config.execution_mode or "smart"
            mobile_device_id = config.mobile_device_id

        valid_modes = ("preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart")
        if execution_mode not in valid_modes:
            logger.warning(f"非法执行模式 '{execution_mode}'，回退到默认值 'smart'")
            execution_mode = "smart"

        # 重试场景（FAILED/STOPPED）：重置计数器和旧执行结果，保证干净重跑
        is_retry = task.status in [3, 4]
        if is_retry:
            await db.execute(
                TestResult.__table__.delete().where(TestResult.task_id == task_id)
            )

        # 标记任务为运行中
        running_result = await db.execute(
            select(TestTask).where(TestTask.id == task_id)
        )
        running_task = running_result.scalars().first()
        running_task.status = 1
        running_task.start_time = utcnow()
        running_task.end_time = None
        running_task.progress = 0
        running_task.success_count = 0
        running_task.fail_count = 0
        await db.commit()

        # TestExecutionEngineV2 内部使用 sync Session API，需独立 sync 会话
        # 性能优化：将 async service 调用放到独立线程，避免 sync_db.query() 阻塞事件循环
        from app.utils.async_sync_bridge import run_async_coro_in_thread
        from app.services.execution_control_manager import execution_controller
        sync_db = PrimarySessionLocal()
        # P1 E-04: 注册执行控制器，支持暂停/恢复
        execution_controller.register(task_id)
        try:
            executor = TestExecutionEngineV2(sync_db)
            try:
                await run_async_coro_in_thread(
                    executor.execute_test_task(
                        task_id=task_id,
                        execution_mode=execution_mode,
                        mobile_device_id=mobile_device_id
                    )
                )
            except Exception as e:
                logger.error("任务执行异常: {}", e, exc_info=True)
                # 异常路径：_mark_running 已 commit，async 会话干净，
                # 直接重新查询并标记失败（status=3=FAILED，非 2=COMPLETED）
                failed_result = await db.execute(
                    select(TestTask).where(TestTask.id == task_id)
                )
                failed_task = failed_result.scalars().first()
                if failed_task:
                    failed_task.status = 3
                    failed_task.end_time = utcnow()
                    await db.commit()
        finally:
            sync_db.close()
            # P1 E-04: 执行结束（正常/异常/停止）后注销控制器
            execution_controller.unregister(task_id)

        return create_response(data={
            "task_id": task_id,
            "status": "running",
            "execution_mode": execution_mode
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("启动任务失败: {}", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="启动任务失败"
        )


@router.delete("/{task_id}", response_model=ApiResponse)
async def delete_test_task(
    task_id: int,
    task: TestTask = Depends(require_task_access),
    db: AsyncSession = Depends(async_get_db)
):
    """删除测试任务（存在性与归属校验由 require_task_access 完成）"""
    await db.delete(task)
    await db.commit()
    return {"message": "测试任务删除成功"}
