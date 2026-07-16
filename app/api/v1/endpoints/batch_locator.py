"""
批量定位器端点模块

本模块定义批量定位器的核心API端点，包括批量录制和状态查询。

路由前缀: /batch-locator
标签: 批量定位器

端点概览:
    - POST /batch-record          - 启动批量定位录制
    - GET  /batch-record-status/{task_id} - 获取批量录制状态

子模块:
    - batch_locator_tasks: 报告获取、任务取消、任务列表

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 批量录制基于测试用例步骤，自动识别页面元素并生成定位器
    - 录制过程异步执行，通过状态接口轮询进度
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.batch_locator_service import BatchLocatorService
from app.core.exception import create_response
from loguru import logger

from app.api.v1.endpoints.batch_locator_tasks import router as tasks_router

router = APIRouter(prefix="/batch-locator", tags=["批量定位器"])

# 注册子模块路由
router.include_router(tasks_router)


class BatchRecordRequest(BaseModel):
    """批量录制请求模型"""
    project_id: int = 0
    case_ids: List[int] = Field(default_factory=list)
    execution_mode: Optional[str] = "smart"
    skip_existing: bool = True
    execute_precondition: bool = True

    @field_validator('case_ids')
    @classmethod
    def validate_case_ids(cls, v: List[int]) -> List[int]:
        if not v:
            return v
        if len(v) > 100:
            raise ValueError(f'一次最多录制100个用例，当前: {len(v)}')
        return v

    @field_validator('execution_mode')
    @classmethod
    def validate_execution_mode(cls, v: str) -> str:
        valid_modes = ('preprocess', 'realtime', 'smart')
        if v not in valid_modes:
            raise ValueError(f'不支持的执行模式: {v}，可选: {valid_modes}')
        return v


class BatchRecordResponse(BaseModel):
    """批量录制启动响应模型（兼容旧测试导出）。"""

    success: bool
    message: str
    case_id: int
    task_id: Optional[str] = None


class BatchRecordStatusResponse(BaseModel):
    """批量录制状态响应模型（兼容旧测试导出）。"""

    case_id: int
    status: str
    progress: float
    total_steps: int
    current_step: Optional[int] = None
    message: Optional[str] = None


@router.post("/batch-record")
async def start_batch_record(
    request: BatchRecordRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """启动批量定位录制"""
    try:
        if request.project_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="项目ID不能为空"
            )
        if not request.case_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="用例ID列表不能为空"
            )

        service = BatchLocatorService(db)
        task_id = await service.start_batch_record(
            project_id=request.project_id,
            case_ids=request.case_ids,
            execution_mode=request.execution_mode,
            user_id=current_user.id
        )

        return create_response(
            data={"task_id": task_id},
            msg="批量录制任务已启动"
        )
    except Exception as e:
        logger.error(f"启动批量录制失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="启动批量录制失败"
        )


@router.get("/batch-record-status/{task_id}")
async def get_batch_record_status(
    task_id: str,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取批量录制状态"""
    service = BatchLocatorService(db)
    status_info = await service.get_batch_status(task_id)

    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    return create_response(data=status_info)
