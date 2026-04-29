"""
测试任务端点模块

本模块定义测试任务的API端点，用于管理测试执行任务的创建、查询和状态控制。

路由前缀: /testTask
标签: 测试任务管理

端点概览:
    - POST  /                     - 创建测试任务
    - GET   /list                 - 获取任务列表
    - GET   /{task_id}            - 获取任务详情
    - PUT   /{task_id}/status     - 更新任务状态
    - DELETE /{task_id}           - 删除任务

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 任务关联项目和测试用例
    - 任务状态: pending/running/completed/failed
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.db.database import get_db
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.test_case import TestCase
from app.models.user import User
from app.api.v1.endpoints.auth import oauth2_scheme, get_current_user
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.core.exception import create_response
from loguru import logger

router = APIRouter(prefix="/test_task", tags=["测试任务管理"])

# 创建任务请求模型
class CreateTaskRequest(BaseModel):
    project_id: int
    task_name: str
    description: Optional[str] = None
    case_ids: List[int] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "project_id": 1,
                "task_name": "Test Task",
                "description": "Description",
                "case_ids": [1, 2, 3]
            }
        }

@router.post("/", response_model=dict)
async def create_test_task(
    request_data: CreateTaskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建测试任务"""
    try:
        project_id = request_data.project_id
        task_name = request_data.task_name
        test_case_ids = request_data.case_ids

        # 创建测试任务（使用当前登录用户的ID）
        new_task = TestTask(
            project_id=project_id,
            task_name=task_name,
            case_ids=test_case_ids or [],
            executor_id=current_user.id,  # 使用当前登录用户ID
            status=0,  # 0: 等待执行
            total_count=len(test_case_ids) if test_case_ids else 0
        )

        db.add(new_task)
        db.flush()  # 获取ID但不提交事务

        # 批量查询测试用例（避免N+1查询）
        if test_case_ids:
            test_cases = db.query(TestCase).filter(
                TestCase.id.in_(test_case_ids),
                TestCase.project_id == project_id
            ).all()
            # 创建ID到用例的映射
            case_map = {tc.id: tc for tc in test_cases}

            # 使用批量插入优化性能（避免逐个db.add）
            from sqlalchemy import insert
            task_results_to_insert = []
            for case_id in test_case_ids:
                test_case = case_map.get(case_id)
                if test_case:
                    task_results_to_insert.append({
                        "task_id": new_task.id,
                        "project_id": project_id,
                        "case_id": case_id,
                        "case_no": test_case.case_no,
                        "exec_status": 0
                    })

            if task_results_to_insert:
                db.bulk_insert_mappings(TestResult, task_results_to_insert)

        db.commit()
        db.refresh(new_task)

        return create_response(data={
            "task_id": new_task.id,
            "task_name": new_task.task_name,
            "project_id": new_task.project_id,
            "total_count": new_task.total_count,
            "create_time": new_task.create_time
        })
    except Exception as e:
        db.rollback()
        logger.error(f"创建测试任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建测试任务失败: {str(e)}"
        )

@router.get("/", response_model=dict)
async def get_test_tasks(
    project_id: int = Query(None, description="项目ID"),
    status: str = Query(None, description="任务状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取测试任务列表"""
    # 构建查询
    query = db.query(TestTask)
    if project_id:
        query = query.filter(TestTask.project_id == project_id)
    if status:
        query = query.filter(TestTask.status == status)

    # 计算偏移量
    offset = (page - 1) * page_size

    # 查询测试任务列表
    test_tasks = query.offset(offset).limit(page_size).all()
    total = query.count()

    # 转换为字典
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

    return {
        "total": total,
        "items": items
    }

@router.get("/{task_id}")
async def get_test_task(
    task_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """获取测试任务详情"""
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试任务不存在"
        )
    
    # 获取任务关联的测试结果
    task_results = db.query(TestResult).filter(
        TestResult.task_id == task_id
    ).all()
    
    return {
        "task": task,
        "results": task_results
    }

@router.post("/{task_id}/start")
async def start_test_task(
    task_id: int,
    config: Optional[dict] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """开始执行测试任务（支持执行模式和设备参数）"""
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )

        if task.status not in [0, 3]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务状态不允许开始执行 (当前状态: {task.status})"
            )

        execution_mode = "smart"
        mobile_device_id = None
        if config:
            execution_mode = config.get("execution_mode", "smart")
            mobile_device_id = config.get("mobile_device_id")

        valid_modes = ("preprocess", "realtime", "smart", "mobile_realtime", "mobile_smart")
        if execution_mode not in valid_modes:
            logger.warning(f"非法执行模式 '{execution_mode}'，回退到默认值 'smart'")
            execution_mode = "smart"

        task.status = 1
        task.start_time = datetime.now()
        db.commit()

        executor = TestExecutionEngineV2(db)

        try:
            await executor.execute_test_task(
                task_id=task_id,
                execution_mode=execution_mode,
                mobile_device_id=mobile_device_id
            )
        except Exception as e:
            logger.error(f"任务执行异常: {e}")
            task.status = 2
            task.end_time = datetime.now()
            db.commit()

        return create_response(data={
            "task_id": task_id,
            "status": "running",
            "execution_mode": execution_mode
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动任务失败: {str(e)}"
        )


@router.post("/{task_id}/run")
async def run_test_task(
    task_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """执行测试任务"""
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试任务不存在"
        )
    
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行测试任务失败: {str(e)}"
        )

@router.get("/{task_id}/summary")
async def get_task_summary(
    task_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """获取任务执行摘要"""
    try:
        from app.models.test_task import TestTask
        from app.models.test_result import TestResult
        from sqlalchemy import case, func

        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

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
            detail=f"获取任务摘要失败: {str(e)}"
        )

@router.delete("/{task_id}")
async def delete_test_task(
    task_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """删除测试任务"""
    task = db.query(TestTask).filter(TestTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试任务不存在"
        )
    
    db.delete(task)
    db.commit()
    
    return {"message": "测试任务删除成功"}