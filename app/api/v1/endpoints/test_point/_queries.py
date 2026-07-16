import json
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_point._helpers import check_project_permission
from app.crud.test_point import get_test_point_by_id
from app.crud.test_point_management import (
    get_test_point_list_stats,
    get_test_points_with_case_count,
    get_test_points_with_case_count_total,
)
from app.db.database import async_get_db, PrimarySessionLocal
from app.models.user import User
from app.schemas.test_point import TestPointResponse
from app.services.ai_analysis_service import aio_analysis_service

router = APIRouter()


@router.post("/analyze")
async def analyze_project(
    request: Any,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # aio_analysis_service.analyze_project 内部使用 sync Session API，
        # 需独立 sync 会话以保证流式生成过程中数据可见性
        from app.utils.async_sync_bridge import iter_async_gen_in_thread
        stream_db = PrimarySessionLocal()
        try:
            async def generate_progress() -> Any:
                try:
                    # 性能优化：将 async generator 放到独立线程执行，避免 sync_db.query() 阻塞事件循环
                    def _agen_factory():
                        return aio_analysis_service.analyze_project(
                            db=stream_db, project_id=request.project_id,
                            user_id=current_user.id, username=current_user.username,
                        )

                    async for progress in iter_async_gen_in_thread(_agen_factory):
                        yield f"data: {json.dumps(progress)}\n\n"
                finally:
                    stream_db.close()

            from fastapi.responses import StreamingResponse
            return StreamingResponse(generate_progress(), media_type="text/event-stream")
        except Exception:
            stream_db.close()
            raise
    except Exception as e:
        logger.error(f"分析项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="分析项目失败"
        )


@router.get("/list/{project_id}")
async def get_test_points(
    project_id: int,
    module: Optional[str] = Query(None, description="模块名称"),
    priority: Optional[int] = Query(None, ge=1, le=3, description="优先级"),
    created_by: Optional[str] = Query(None, description="创建人用户名"),
    requirement_id: Optional[int] = Query(None, description="关联需求ID"),
    keyword: Optional[str] = Query(None, description="关键词"),
    created_from: Optional[date] = Query(None, description="创建开始日期"),
    created_to: Optional[date] = Query(None, description="创建结束日期"),
    sort_by: str = Query("create_time", description="排序字段"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        skip = (page - 1) * page_size

        def _list(sync_db):
            test_points = get_test_points_with_case_count(
                db=sync_db, project_id=project_id, user_id=current_user.id,
                module=module, priority=priority, created_by=created_by,
                requirement_id=requirement_id, keyword=keyword,
                created_from=created_from, created_to=created_to,
                skip=skip, limit=page_size, sort_by=sort_by, sort_order=sort_order,
            )
            total = get_test_points_with_case_count_total(
                db=sync_db, project_id=project_id, user_id=current_user.id,
                module=module, priority=priority, created_by=created_by,
                requirement_id=requirement_id, keyword=keyword,
                created_from=created_from, created_to=created_to,
            )
            stats = get_test_point_list_stats(
                db=sync_db, project_id=project_id, user_id=current_user.id,
                module=module, created_by=created_by,
                requirement_id=requirement_id, keyword=keyword,
                created_from=created_from, created_to=created_to,
            )
            items = [
                TestPointResponse(
                    id=point.id, project_id=point.project_id,
                    requirement_id=point.requirement_id, module=point.module,
                    point=point.point,
                    priority=point.priority, ai_prompt=point.ai_prompt,
                    capability_id=point.capability_id, version=point.version, status=point.status,
                    create_time=point.create_time, created_by=point.created_by,
                    test_case_count=case_count,
                )
                for point, case_count in test_points
            ]
            return {
                "total": total, "items": items,
                "page": page, "page_size": page_size, "stats": stats,
            }

        data = await db.run_sync(_list)
        return {"code": 200, "message": "获取成功", "data": data}
    except Exception as e:
        logger.error(f"获取测试点列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取测试点列表失败",
        )


@router.get("/detail/{test_point_id}", response_model=TestPointResponse)
async def get_test_point_detail(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        from app.crud.test_point_management import get_test_cases_by_test_point_total

        def _detail(sync_db) -> TestPointResponse:
            check_project_permission(sync_db, project_id, current_user.id)
            test_point = get_test_point_by_id(sync_db, test_point_id, project_id)
            if not test_point:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在"
                )
            test_case_count = get_test_cases_by_test_point_total(
                db=sync_db, project_id=project_id,
                user_id=current_user.id, test_point_id=test_point_id,
            )
            return TestPointResponse(
                id=test_point.id, project_id=test_point.project_id,
                requirement_id=test_point.requirement_id, module=test_point.module,
                point=test_point.point,
                priority=test_point.priority, ai_prompt=test_point.ai_prompt,
                capability_id=test_point.capability_id, version=test_point.version, status=test_point.status,
                create_time=test_point.create_time, created_by=test_point.created_by,
                test_case_count=test_case_count,
            )

        return await db.run_sync(_detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测试点详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取测试点详情失败",
        )
