import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db, AsyncPrimarySessionLocal
from app.schemas.common import ApiResponse
from app.models.project import Project
from app.models.user import User
from app.services.case_refresh_service import CaseRefreshService

router = APIRouter(tags=["用例保鲜"])


class ReviewSuggestionRequest(BaseModel):
    action: str = Field(..., description="审核操作: approve/reject")
    reject_reason: Optional[str] = Field(None, description="驳回原因")


class ScanStaleRequest(BaseModel):
    project_id: int = Field(..., description="项目ID")


async def _verify_project_ownership(
    project_id: int, current_user: User, db: AsyncSession
) -> Project:
    """校验当前用户对项目的所有权，不通过时抛 404/403。"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
    return project


@router.get("/projects/{project_id}/refresh-suggestions", response_model=ApiResponse)
async def list_refresh_suggestions(
    project_id: int,
    page: int = 1,
    page_size: int = 20,
    suggestion_status: Optional[str] = None,
    review_status: Optional[str] = None,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _verify_project_ownership(project_id, current_user, db)
    service = CaseRefreshService(db)
    result = await service.list_suggestions(
        project_id, page, page_size, suggestion_status, review_status
    )
    return create_response(data=result)


@router.get("/projects/{project_id}/refresh-suggestions/stats", response_model=ApiResponse)
async def get_refresh_suggestions_stats(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _verify_project_ownership(project_id, current_user, db)
    service = CaseRefreshService(db)
    stats = await service.get_suggestions_stats(project_id)
    return create_response(data=stats)


@router.post("/refresh-suggestions/{suggestion_id}/review", response_model=ApiResponse)
async def review_refresh_suggestion(
    suggestion_id: int,
    request: ReviewSuggestionRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    service = CaseRefreshService(db)
    suggestion = await service.get_suggestion_by_id(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="保鲜建议不存在")
    case = await service.get_case_by_id(suggestion.case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联用例不存在")
    await _verify_project_ownership(case.project_id, current_user, db)
    try:
        suggestion = await service.review_suggestion(
            suggestion_id=suggestion_id,
            action=request.action,
            reviewer_id=current_user.id,
            reviewer_name=current_user.username,
            reject_reason=request.reject_reason,
        )
        await db.commit()
        return create_response(data=service._suggestion_to_dict(suggestion), msg="审核完成")
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"审核保鲜建议失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="审核失败"
        )


@router.post("/projects/{project_id}/scan-stale-cases", response_model=ApiResponse)
async def scan_stale_cases(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _verify_project_ownership(project_id, current_user, db)
    service = CaseRefreshService(db)
    stale_cases = await service.scan_stale_cases(project_id)
    return create_response(data={"stale_cases": stale_cases, "count": len(stale_cases)})


async def _run_auto_refresh_async(project_id: int, max_cases: int) -> None:
    """后台自动保鲜任务，使用独立 AsyncSession。

    fire-and-forget 模式：通过 asyncio.create_task 触发，
    内部使用 AsyncPrimarySessionLocal 创建独立会话，异常仅记录日志。
    """
    async with AsyncPrimarySessionLocal() as refresh_db:
        try:
            service = CaseRefreshService(refresh_db)
            await service.auto_scan_and_suggest(project_id, max_cases)
            await refresh_db.commit()
        except Exception as exc:
            await refresh_db.rollback()
            logger.error(f"后台自动保鲜失败: {exc}")


@router.post("/projects/{project_id}/auto-refresh", response_model=ApiResponse)
async def auto_refresh_suggestions(
    project_id: int,
    max_cases: int = 10,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _verify_project_ownership(project_id, current_user, db)
    service = CaseRefreshService(db)
    stale_cases = await service.scan_stale_cases(project_id)
    if not stale_cases:
        return create_response(
            data={"created": [], "errors": [], "total_scanned": 0}, msg="无过期用例"
        )

    asyncio.create_task(_run_auto_refresh_async(project_id, max_cases))
    return create_response(
        data={"total_scanned": len(stale_cases), "status": "processing"},
        msg=f"已提交后台处理，共 {len(stale_cases)} 条过期用例",
    )
