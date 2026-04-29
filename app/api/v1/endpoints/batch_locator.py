"""
批量元素定位API

提供测试用例级别的批量元素定位补充接口
"""
from typing import Optional
"""
批量定位器端点模块

本模块定义批量元素定位器的API端点，支持批量识别和验证UI元素定位器。

路由前缀: /batch-locator
标签: 批量定位器

端点概览:
    - POST /validate   - 批量验证定位器有效性
    - POST /suggest    - AI推荐定位器
    - POST /extract    - 从HTML中提取定位器

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 支持XPath、CSS Selector、ID等多种定位策略
    - AI推荐基于页面结构分析
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.test_case import TestCase
from app.api.v1.endpoints.auth import oauth2_scheme, get_current_user
from app.core.permissions import require_technical_view
from app.services.batch_locator_service import (
    BatchLocatorService,
    BatchTaskManager,
    batch_record_locators,
    BatchRecordStatus
)
from app.core.websocket import manager as ws_manager

router = APIRouter(prefix="/batch-locator", tags=["批量元素定位"])

# 全局任务管理器
task_manager = BatchTaskManager()


class BatchRecordRequest(BaseModel):
    skip_existing: bool = Field(
        default=True,
        description="是否跳过已有定位的步骤",
        example=True
    )
    execute_precondition: bool = Field(
        default=True,
        description="是否执行前置操作（启动浏览器并登录）",
        example=True
    )
    use_mcp: Optional[bool] = Field(None, description="是否使用Playwright MCP定位，None时使用系统配置")


class BatchRecordResponse(BaseModel):
    """批量记录响应"""
    success: bool
    message: str
    case_id: int
    task_id: Optional[str] = None


class BatchRecordStatusResponse(BaseModel):
    """批量记录状态响应"""
    case_id: int
    status: str
    progress: float  # 0-100
    current_step: Optional[int] = None
    total_steps: int
    message: Optional[str] = None


MAX_CONCURRENT_TASKS = 2


@router.post("/cases/{case_id}/batch-record", response_model=BatchRecordResponse)
async def start_batch_record(
    case_id: int,
    request: BatchRecordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technical_view)
):
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    existing_task = task_manager.get_task(case_id)
    if existing_task:
        report = existing_task.get_report()
        if report and report.status == BatchRecordStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该用例已有正在执行的批量记录任务"
            )

    running_count = len(task_manager.get_all_tasks())
    if running_count >= MAX_CONCURRENT_TASKS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"同时运行的批量定位任务数量已达上限({MAX_CONCURRENT_TASKS})"
        )

    async def progress_callback(data: dict):
        try:
            await ws_manager.broadcast_to_execution(
                execution_id=f"batch_{case_id}",
                message={
                    "type": "batch_locator_progress",
                    "case_id": case_id,
                    **data
                }
            )
        except Exception as e:
            logger.warning(f"WebSocket推送失败: case_id={case_id}, error={e}")

    service = BatchLocatorService(
        progress_callback=progress_callback,
        use_mcp=request.use_mcp
    )

    task_manager.register_task(case_id, service)

    async def run_batch_task():
        try:
            report = await service.batch_record_locators(
                case_id=case_id,
                skip_existing=request.skip_existing,
                execute_precondition=request.execute_precondition
            )
            logger.info(f"批量记录任务完成: case_id={case_id}, status={report.status}")

            if report.status in ["failed", "cancelled"]:
                try:
                    await ws_manager.broadcast_to_execution(
                        execution_id=f"batch_{case_id}",
                        message={
                            "type": "batch_locator_error",
                            "case_id": case_id,
                            "status": report.status,
                            "error": report.error_message
                        }
                    )
                except Exception as e:
                    logger.warning(f"WebSocket错误推送失败: {e}")

        except Exception as e:
            logger.exception(f"批量记录任务失败: case_id={case_id}, error={e}")
            try:
                await ws_manager.broadcast_to_execution(
                    execution_id=f"batch_{case_id}",
                    message={
                        "type": "batch_locator_error",
                        "case_id": case_id,
                        "status": "failed",
                        "error": str(e)
                    }
                )
            except Exception as ws_e:
                logger.warning(f"WebSocket错误推送失败: {ws_e}")
        finally:
            task_manager.unregister_task(case_id)

    import asyncio
    asyncio.create_task(run_batch_task())

    logger.info(f"批量记录任务已启动: case_id={case_id}, user={current_user.username}")

    return BatchRecordResponse(
        success=True,
        message="批量记录任务已启动",
        case_id=case_id,
        task_id=f"batch_{case_id}"
    )


@router.get("/cases/{case_id}/batch-record-status", response_model=BatchRecordStatusResponse)
async def get_batch_record_status(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technical_view)
):
    """
    获取批量记录任务状态
    
    权限：仅测试工程师、管理员可访问
    
    Args:
        case_id: 测试用例ID
        
    Returns:
        任务状态和进度
    """
    # 验证测试用例存在
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )
    
    # 获取任务
    service = task_manager.get_task(case_id)
    if not service:
        return BatchRecordStatusResponse(
            case_id=case_id,
            status="not_found",
            progress=0,
            total_steps=0,
            message="没有正在执行的任务"
        )
    
    # 获取报告
    report = service.get_report()
    if not report:
        return BatchRecordStatusResponse(
            case_id=case_id,
            status="unknown",
            progress=0,
            total_steps=0,
            message="任务状态未知"
        )
    
    # 计算进度
    if report.total_steps > 0:
        progress = (len(report.step_results) / report.total_steps) * 100
    else:
        progress = 0
    
    # 获取当前步骤
    current_step = None
    if report.step_results:
        current_step = report.step_results[-1].step_number
    
    return BatchRecordStatusResponse(
        case_id=case_id,
        status=report.status.value,
        progress=round(progress, 2),
        current_step=current_step,
        total_steps=report.total_steps,
        message=report.error_message
    )


@router.get("/cases/{case_id}/batch-record-report")
async def get_batch_record_report(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technical_view)
):
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    report = task_manager.get_report(case_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到批量记录报告"
        )

    return report.to_dict()


@router.post("/cases/{case_id}/batch-record-cancel")
async def cancel_batch_record(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technical_view)
):
    """
    取消批量记录任务
    
    权限：仅测试工程师、管理员可访问
    
    Args:
        case_id: 测试用例ID
        
    Returns:
        取消结果
    """
    # 验证测试用例存在
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )
    
    # 取消任务
    success = task_manager.cancel_task(case_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到正在执行的任务"
        )
    
    logger.info(f"批量记录任务已取消: case_id={case_id}, user={current_user.username}")
    
    return {
        "success": True,
        "message": "任务已取消",
        "case_id": case_id
    }


@router.get("/batch-tasks")
async def list_batch_tasks(
    current_user: User = Depends(require_technical_view)
):
    """
    获取所有批量任务列表
    
    权限：仅测试工程师、管理员可访问
    
    Returns:
        批量任务列表
    """
    tasks = task_manager.get_all_tasks()
    
    result = []
    for case_id, service in tasks.items():
        report = service.get_report()
        if report:
            result.append({
                "case_id": case_id,
                "case_title": report.case_title,
                "status": report.status.value,
                "progress": round(
                    (len(report.step_results) / report.total_steps * 100), 2
                ) if report.total_steps > 0 else 0,
                "total_steps": report.total_steps,
                "completed_steps": len(report.step_results)
            })
    
    return result
