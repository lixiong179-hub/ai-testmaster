import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_point._helpers import check_project_permission
from app.crud.test_point import create_test_point, get_test_point_by_id
from app.crud.test_point_management import (
    get_requirements_by_project,
    get_test_cases_by_test_point,
    get_test_cases_by_test_point_total,
)
from app.db.database import async_get_db
from app.models.user import User
from app.schemas.test_point import (
    TestPointBatchGenerateRequest,
    TestPointCreate,
    TestPointRelatedCaseResponse,
    TestPointRequirementOptionResponse,
    TestPointResponse,
)
from app.services.test_case_generation import TestCaseGenerationService

router = APIRouter()


@router.post("/", response_model=TestPointResponse)
async def create_test_point_item(
    request: TestPointCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> TestPointResponse:
    def _create(sync_db: Session):
        check_project_permission(sync_db, request.project_id, current_user.id)
        return create_test_point(
            db=sync_db, project_id=request.project_id, module=request.module,
            point=request.point, priority=request.priority,
            ai_prompt=request.ai_prompt, created_by=current_user.username,
            capability_id=request.capability_id, status=request.status,
        )

    created = await db.run_sync(_create)
    return TestPointResponse(
        id=created.id, project_id=created.project_id,
        requirement_id=created.requirement_id, module=created.module,
        point=created.point,
        priority=created.priority, ai_prompt=created.ai_prompt,
        capability_id=created.capability_id, version=created.version, status=created.status,
        create_time=created.create_time, created_by=created.created_by,
        test_case_count=0,
    )


@router.get("/{test_point_id}/test-cases")
async def get_related_test_cases(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    skip = (page - 1) * page_size

    def _query(sync_db: Session):
        check_project_permission(sync_db, project_id, current_user.id)
        test_point = get_test_point_by_id(sync_db, test_point_id, project_id)
        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在"
            )
        items = get_test_cases_by_test_point(
            db=sync_db, project_id=project_id, user_id=current_user.id,
            test_point_id=test_point_id, skip=skip, limit=page_size,
        )
        total = get_test_cases_by_test_point_total(
            db=sync_db, project_id=project_id, user_id=current_user.id,
            test_point_id=test_point_id,
        )
        return items, total

    items, total = await db.run_sync(_query)
    return {
        "code": 200, "message": "获取成功",
        "data": {
            "total": total,
            "items": [TestPointRelatedCaseResponse.model_validate(i) for i in items],
        },
    }


@router.get("/requirements/{project_id}")
async def get_test_point_requirements(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _query(sync_db: Session):
        check_project_permission(sync_db, project_id, current_user.id)
        return get_requirements_by_project(
            db=sync_db, project_id=project_id, user_id=current_user.id,
        )

    requirements = await db.run_sync(_query)
    return {
        "code": 200, "message": "获取成功",
        "data": {
            "items": [
                TestPointRequirementOptionResponse(
                    id=item.id, req_no=item.req_no, title=item.title,
                )
                for item in requirements
            ],
        },
    }


@router.post("/batch-generate-cases/stream")
async def batch_generate_test_cases_by_points(
    request: TestPointBatchGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    def _check(sync_db: Session):
        check_project_permission(sync_db, request.project_id, current_user.id)

    await db.run_sync(_check)

    async def generate_progress() -> Any:
        from app.db.database import PrimarySessionLocal
        from app.utils.async_sync_bridge import iter_async_gen_in_thread
        stream_db = PrimarySessionLocal()
        try:
            service = TestCaseGenerationService(stream_db)
            try:
                # 性能优化：将 async generator 放到独立线程执行，避免 sync_db.query() 阻塞事件循环
                def _agen_factory():
                    return service.generate_test_cases_batch(
                        project_id=request.project_id, user_id=current_user.id,
                        test_point_ids=request.test_point_ids or None, case_type=request.case_type,
                    )

                async for progress in iter_async_gen_in_thread(_agen_factory):
                    yield f"data: {json.dumps(progress)}\n\n"
            except Exception as exc:
                logger.error(f"测试点批量生成测试用例失败: {exc}")
                yield "data: " + json.dumps(
                    {"progress": 100, "message": "生成失败", "status": "error"}
                ) + "\n\n"
            finally:
                yield "data: [DONE]\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(generate_progress(), media_type="text/event-stream")
