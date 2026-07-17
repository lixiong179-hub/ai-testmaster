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
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
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

from app.api.v1.endpoints.test_task_exec import router as exec_router

router = APIRouter(prefix="/test-task", tags=["测试任务管理"])

# 注册子模块路由
router.include_router(exec_router)


def _verify_project_access(
    db, project_id: int, current_user: User
) -> None:
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
    project = db.query(Project).filter(
        Project.id == task.project_id,
        Project.user_id == current_user.id
    ).first()
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

        def _create(sync_db) -> dict:
            _verify_project_access(sync_db, project_id, current_user)
            new_task = TestTask(
                project_id=project_id,
                task_name=task_name,
                case_ids=test_case_ids or [],
                executor_id=current_user.id,
                status=0,
                total_count=len(test_case_ids) if test_case_ids else 0
            )
            sync_db.add(new_task)
            sync_db.flush()

            if test_case_ids:
                test_cases = sync_db.query(TestCase).filter(
                    TestCase.id.in_(test_case_ids),
                    TestCase.project_id == project_id,
                    TestCase.is_deleted.is_(False)
                ).all()
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
                    sync_db.bulk_insert_mappings(TestResult, task_results_to_insert)

            sync_db.commit()
            sync_db.refresh(new_task)
            return {
                "task_id": new_task.id,
                "task_name": new_task.task_name,
                "project_id": new_task.project_id,
                "total_count": new_task.total_count,
                "create_time": new_task.create_time
            }

        data = await db.run_sync(_create)
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
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试任务列表"""
    def _list(sync_db) -> dict:
        if project_id is not None:
            _verify_project_access(sync_db, project_id, current_user)
            query = sync_db.query(TestTask).filter(TestTask.project_id == project_id)
        else:
            query = sync_db.query(TestTask).join(
                Project,
                Project.id == TestTask.project_id
            ).filter(Project.user_id == current_user.id)
        if task_status is not None:
            query = query.filter(TestTask.status == task_status)
        offset = (page - 1) * page_size
        test_tasks = query.order_by(TestTask.id.desc()).offset(offset).limit(page_size).all()
        total = query.count()
        items = []
        for task in test_tasks:
            items.append({
                "id": task.id,
                "task_name": task.task_name,
                "project_id": task.project_id,
                "case_ids": task.case_ids or [],
                "executor_id": task.executor_id,
                "status": task.status,
                "total_count": task.total_count,
                "success_count": getattr(task, 'success_count', 0),
                "fail_count": getattr(task, 'fail_count', 0),
                "progress": getattr(task, 'progress', 0),
                "create_time": task.create_time,
                "update_time": getattr(task, 'update_time', None)
            })
        return {"total": total, "items": items}

    data = await db.run_sync(_list)
    return create_response(data=data)


@router.get("/{task_id}", response_model=ApiResponse)
async def get_test_task(
    task_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试任务详情"""
    def _detail(sync_db) -> dict:
        task = sync_db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试任务不存在"
            )
        _verify_task_access(sync_db, task, current_user)
        task_results = sync_db.query(TestResult).filter(
            TestResult.task_id == task_id
        ).all()
        vis_service = VisibilityConfigService()
        vis_config = vis_service.get_project_config(sync_db, task.project_id)
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

    return await db.run_sync(_detail)


@router.post("/{task_id}/start", response_model=ApiResponse)
async def start_test_task(
    task_id: int,
    config: Optional[TaskStartConfig] = None,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """开始执行测试任务（支持执行模式和设备参数）"""
    try:
        def _prepare(sync_db) -> TestTask:
            task = sync_db.query(TestTask).filter(TestTask.id == task_id).first()
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="任务不存在"
                )
            _verify_task_access(sync_db, task, current_user)
            if task.status not in [0, 3]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"任务状态不允许开始执行 (当前状态: {task.status})"
                )
            return task

        execution_mode = "smart"
        mobile_device_id = None
        if config:
            execution_mode = config.execution_mode or "smart"
            mobile_device_id = config.mobile_device_id

        valid_modes = ("preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart")
        if execution_mode not in valid_modes:
            logger.warning(f"非法执行模式 '{execution_mode}'，回退到默认值 'smart'")
            execution_mode = "smart"

        task = await db.run_sync(_prepare)

        def _mark_running(sync_db):
            t = sync_db.query(TestTask).filter(TestTask.id == task_id).first()
            t.status = 1
            t.start_time = utcnow()
            sync_db.commit()
            return t
        await db.run_sync(_mark_running)

        # TestExecutionEngineV2 内部使用 sync Session API，需独立 sync 会话
        # 性能优化：将 async service 调用放到独立线程，避免 sync_db.query() 阻塞事件循环
        from app.utils.async_sync_bridge import run_async_coro_in_thread
        sync_db = PrimarySessionLocal()
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

                def _mark_failed(failed_db):
                    t = failed_db.query(TestTask).filter(TestTask.id == task_id).first()
                    if t:
                        t.status = 2
                        t.end_time = utcnow()
                        failed_db.commit()
                # 使用 async 会话的 sync session 更新状态，保证事务可见性
                await db.run_sync(_mark_failed)
        finally:
            sync_db.close()

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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """删除测试任务"""
    def _delete(sync_db):
        task = sync_db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试任务不存在"
            )
        _verify_task_access(sync_db, task, current_user)
        sync_db.delete(task)
        sync_db.commit()

    await db.run_sync(_delete)
    return {"message": "测试任务删除成功"}
