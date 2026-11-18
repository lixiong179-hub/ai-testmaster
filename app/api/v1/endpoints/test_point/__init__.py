"""测试点管理端点包。

路由处理函数已内联在本模块（原 `_queries.py` / `_mutations.py` / `_management.py`
已合并），项目权限校验下沉至 `app.services.test_point.helpers`。

`check_project_permission` / `check_project_permission_async` 继续由本模块导出，
供 test_point_import / test_point_import_stream 等模块复用。
"""

import asyncio
import json
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.crud.test_point import batch_create_test_points
from app.crud.test_point_management import (
    get_test_point_list_stats,
    get_test_points_with_case_count,
    get_test_points_with_case_count_total,
)
from app.db.database import PrimarySessionLocal, get_db
from app.models.enums import TestPointStatus
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.test_point import TestPoint as TestPointModel
from app.models.user import User
from app.schemas.test_point import (
    TestPointBatchGenerateRequest,
    TestPointCreate,
    TestPointRelatedCaseResponse,
    TestPointRequirementOptionResponse,
    TestPointResponse,
    TestPointUpdate,
)
from app.services.ai_analysis_service import aio_analysis_service
from app.services.test_case_generation import TestCaseGenerationService
from app.services.test_point.helpers import (
    check_project_permission,
    check_project_permission_async,
)

router = APIRouter(prefix="/test-point", tags=["测试点管理"])


@router.post("/analyze")
async def analyze_project(
    request: Any,
    db: Session = Depends(get_db),
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
                            db=stream_db,
                            project_id=request.project_id,
                            user_id=current_user.id,
                            username=current_user.username,
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="分析项目失败")


@router.get("/list/{project_id}")
async def get_test_points(
    project_id: int,
    module: str | None = Query(None, description="模块名称"),
    priority: int | None = Query(None, ge=1, le=3, description="优先级"),
    created_by: str | None = Query(None, description="创建人用户名"),
    requirement_id: int | None = Query(None, description="关联需求ID"),
    keyword: str | None = Query(None, description="关键词"),
    created_from: date | None = Query(None, description="创建开始日期"),
    created_to: date | None = Query(None, description="创建结束日期"),
    sort_by: str = Query("create_time", description="排序字段"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        skip = (page - 1) * page_size

        def _list(sync_db):
            test_points = get_test_points_with_case_count(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                module=module,
                priority=priority,
                created_by=created_by,
                requirement_id=requirement_id,
                keyword=keyword,
                created_from=created_from,
                created_to=created_to,
                skip=skip,
                limit=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            total = get_test_points_with_case_count_total(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                module=module,
                priority=priority,
                created_by=created_by,
                requirement_id=requirement_id,
                keyword=keyword,
                created_from=created_from,
                created_to=created_to,
            )
            stats = get_test_point_list_stats(
                db=sync_db,
                project_id=project_id,
                user_id=current_user.id,
                module=module,
                created_by=created_by,
                requirement_id=requirement_id,
                keyword=keyword,
                created_from=created_from,
                created_to=created_to,
            )
            items = [
                TestPointResponse(
                    id=point.id,
                    project_id=point.project_id,
                    requirement_id=point.requirement_id,
                    module=point.module,
                    point=point.point,
                    priority=point.priority,
                    ai_prompt=point.ai_prompt,
                    capability_id=point.capability_id,
                    version=point.version,
                    status=point.status,
                    create_time=point.create_time,
                    created_by=point.created_by,
                    test_case_count=case_count,
                )
                for point, case_count in test_points
            ]
            return {
                "total": total,
                "items": items,
                "page": page,
                "page_size": page_size,
                "stats": stats,
            }

        data = _list(db)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        check_project_permission(db, project_id, current_user.id)
        # 内联 async 查询替代 get_test_point_by_id sync crud
        tp_result = await asyncio.to_thread(
            db.execute,
            select(TestPoint).where(
                TestPoint.id == test_point_id,
                TestPoint.project_id == project_id,
            ),
        )
        test_point = tp_result.scalars().first()
        if not test_point:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在")
        # 内联聚合查询替代 get_test_cases_by_test_point_total sync crud
        count_result = await asyncio.to_thread(
            db.execute,
            select(func.count(TestCase.id))
            .join(Project, Project.id == TestCase.project_id)
            .where(
                TestCase.project_id == project_id,
                TestCase.test_point_id == test_point_id,
                TestCase.is_deleted.is_(False),
                Project.user_id == current_user.id,
            ),
        )
        test_case_count = count_result.scalar() or 0
        return TestPointResponse(
            id=test_point.id,
            project_id=test_point.project_id,
            requirement_id=test_point.requirement_id,
            module=test_point.module,
            point=test_point.point,
            priority=test_point.priority,
            ai_prompt=test_point.ai_prompt,
            capability_id=test_point.capability_id,
            version=test_point.version,
            status=test_point.status,
            create_time=test_point.create_time,
            created_by=test_point.created_by,
            test_case_count=test_case_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测试点详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取测试点详情失败",
        )


@router.post("/batch-save")
async def batch_save_test_points(
    project_id: int = Query(..., description="项目ID"),
    test_points: list[dict[str, Any]] = Body(..., description="测试点列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    max_batch_size = 200
    try:
        if not test_points or not isinstance(test_points, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="测试点列表不能为空")
        if len(test_points) > max_batch_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次保存数量不能超过{max_batch_size}个",
            )
        valid_points = []
        for i, item in enumerate(test_points):
            if not isinstance(item, dict):
                logger.warning(f"跳过无效数据项[{i}]: 非字典类型")
                continue
            module = str(item.get("module", "")).strip()
            point = str(item.get("point", "")).strip()
            if not module or not point:
                logger.warning(f"跳过数据项[{i}]: 缺少必填字段(module/point)")
                continue
            if len(module) > 100 or len(point) > 500:
                logger.warning(f"跳过数据项[{i}]: 字段超长")
                continue
            try:
                priority = int(item.get("priority", 2))
                if priority < 1 or priority > 3:
                    priority = 2
            except (ValueError, TypeError):
                priority = 2
            valid_points.append(
                {
                    "module": module,
                    "point": point,
                    "priority": priority,
                    "ai_prompt": item.get("ai_prompt"),
                }
            )
        if not valid_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点数据可保存",
            )

        check_project_permission(db, project_id, current_user.id)
        saved = await asyncio.to_thread(
            batch_create_test_points,
            db=db,
            project_id=project_id,
            test_points_data=valid_points,
            created_by=current_user.username,
        )
        data = {
            "saved_count": len(saved),
            "total_submitted": len(valid_points),
            "items": [{"id": tp.id, "module": tp.module, "point": tp.point, "priority": tp.priority} for tp in saved],
        }
        logger.info(
            f"批量保存测试点成功: {data['saved_count']}/{data['total_submitted']} 个 (用户: {current_user.username})"
        )
        return {
            "code": 200,
            "message": f"成功保存 {data['saved_count']} 个测试点",
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量保存测试点失败: {e}")
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存失败")


@router.put("/{test_point_id}")
async def update_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    update_data: TestPointUpdate = Body(..., description="更新数据"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        check_project_permission(db, project_id, current_user.id)

        result = await asyncio.to_thread(
            db.execute,
            select(TestPointModel).where(
                TestPointModel.id == test_point_id,
                TestPointModel.project_id == project_id,
            ),
        )
        test_point = result.scalars().first()
        if not test_point:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在")
        if update_data.module is not None:
            test_point.module = update_data.module
        if update_data.point is not None:
            test_point.point = update_data.point
        if update_data.priority is not None:
            test_point.priority = update_data.priority
        if update_data.ai_prompt is not None:
            test_point.ai_prompt = update_data.ai_prompt
        if update_data.status is not None:
            test_point.status = update_data.status
        test_point.version = (test_point.version or 1) + 1
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, test_point)
        data = TestPointResponse(
            id=test_point.id,
            project_id=test_point.project_id,
            requirement_id=test_point.requirement_id,
            module=test_point.module,
            point=test_point.point,
            priority=test_point.priority,
            ai_prompt=test_point.ai_prompt,
            capability_id=test_point.capability_id,
            version=test_point.version,
            status=test_point.status,
            create_time=test_point.create_time,
            created_by=test_point.created_by,
            test_case_count=0,
        )
        logger.info(f"用户 {current_user.username} 更新了测试点 {test_point_id}")
        return {"code": 200, "message": "更新成功", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新测试点失败: {e}", exc_info=True)
        await asyncio.to_thread(db.rollback)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


@router.delete("/batch")
async def batch_delete_test_points(
    project_id: int = Query(..., description="项目ID"),
    ids: list[int] = Body(..., description="要删除的测试点ID列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    max_batch_delete = 100
    try:
        if not ids or not isinstance(ids, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供有效的ID列表")
        unique_ids = list(set(filter(lambda x: isinstance(x, int) and x > 0, ids)))
        if len(unique_ids) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有有效的测试点ID")
        if len(unique_ids) > max_batch_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次删除数量不能超过{max_batch_delete}个（当前{len(unique_ids)}个）",
            )

        check_project_permission(db, project_id, current_user.id)
        result = await asyncio.to_thread(
            db.execute,
            delete(TestPointModel).where(
                TestPointModel.id.in_(unique_ids),
                TestPointModel.project_id == project_id,
            ),
        )
        deleted_count = result.rowcount or 0
        await asyncio.to_thread(db.commit)
        logger.info(f"用户 {current_user.username} 批量删除了 {deleted_count} 个测试点")
        return {
            "code": 200,
            "message": f"成功删除 {deleted_count} 个测试点",
            "data": {"deleted_count": deleted_count, "requested_count": len(unique_ids)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除测试点失败: {e}", exc_info=True)
        await asyncio.to_thread(db.rollback)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


@router.delete("/{test_point_id}")
async def delete_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        check_project_permission(db, project_id, current_user.id)

        result = await asyncio.to_thread(
            db.execute,
            select(TestPointModel).where(
                TestPointModel.id == test_point_id,
                TestPointModel.project_id == project_id,
            ),
        )
        test_point = result.scalars().first()
        if test_point:
            await asyncio.to_thread(db.delete, test_point)
            await asyncio.to_thread(db.commit)
        logger.info(f"用户 {current_user.username} 删除了测试点 {test_point_id}")
        return {"code": 200, "message": "删除成功", "data": {"id": test_point_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除测试点失败: {e}", exc_info=True)
        await asyncio.to_thread(db.rollback)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


@router.post("/", response_model=TestPointResponse)
async def create_test_point_item(
    request: TestPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestPointResponse:
    check_project_permission(db, request.project_id, current_user.id)

    created = TestPoint(
        project_id=request.project_id,
        module=request.module,
        point=request.point,
        priority=request.priority,
        ai_prompt=request.ai_prompt,
        created_by=current_user.username,
        requirement_id=None,
        capability_id=request.capability_id,
        status=request.status or TestPointStatus.ACTIVE.value,
    )
    db.add(created)
    await asyncio.to_thread(db.commit)
    await asyncio.to_thread(db.refresh, created)
    return TestPointResponse(
        id=created.id,
        project_id=created.project_id,
        requirement_id=created.requirement_id,
        module=created.module,
        point=created.point,
        priority=created.priority,
        ai_prompt=created.ai_prompt,
        capability_id=created.capability_id,
        version=created.version,
        status=created.status,
        create_time=created.create_time,
        created_by=created.created_by,
        test_case_count=0,
    )


@router.get("/{test_point_id}/test-cases")
async def get_related_test_cases(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_project_permission(db, project_id, current_user.id)
    skip = (page - 1) * page_size

    tp_result = await asyncio.to_thread(
        db.execute,
        select(TestPoint).where(
            TestPoint.id == test_point_id,
            TestPoint.project_id == project_id,
        ),
    )
    test_point = tp_result.scalars().first()
    if not test_point:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在")

    items_result = await asyncio.to_thread(
        db.execute,
        select(TestCase)
        .join(Project, Project.id == TestCase.project_id)
        .where(
            TestCase.project_id == project_id,
            TestCase.test_point_id == test_point_id,
            TestCase.is_deleted.is_(False),
            Project.user_id == current_user.id,
        )
        .order_by(desc(TestCase.create_time), desc(TestCase.id))
        .offset(skip)
        .limit(page_size),
    )
    items = items_result.scalars().all()

    total_result = await asyncio.to_thread(
        db.execute,
        select(func.count(TestCase.id))
        .join(Project, Project.id == TestCase.project_id)
        .where(
            TestCase.project_id == project_id,
            TestCase.test_point_id == test_point_id,
            TestCase.is_deleted.is_(False),
            Project.user_id == current_user.id,
        ),
    )
    total = total_result.scalar() or 0

    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "total": total,
            "items": [TestPointRelatedCaseResponse.model_validate(i) for i in items],
        },
    }


@router.get("/requirements/{project_id}")
async def get_test_point_requirements(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_project_permission(db, project_id, current_user.id)

    result = await asyncio.to_thread(
        db.execute,
        select(Requirement)
        .join(Project, Project.id == Requirement.project_id)
        .where(
            Requirement.project_id == project_id,
            Project.user_id == current_user.id,
        )
        .order_by(desc(Requirement.create_time), desc(Requirement.id)),
    )
    requirements = result.scalars().all()

    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "items": [
                TestPointRequirementOptionResponse(
                    id=item.id,
                    req_no=item.req_no,
                    title=item.title,
                )
                for item in requirements
            ],
        },
    }


@router.post("/batch-generate-cases/stream")
async def batch_generate_test_cases_by_points(
    request: TestPointBatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    check_project_permission(db, request.project_id, current_user.id)

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
                        project_id=request.project_id,
                        user_id=current_user.id,
                        test_point_ids=request.test_point_ids or None,
                        case_type=request.case_type,
                    )

                async for progress in iter_async_gen_in_thread(_agen_factory):
                    yield f"data: {json.dumps(progress)}\n\n"
            except Exception as exc:
                logger.error(f"测试点批量生成测试用例失败: {exc}")
                yield "data: " + json.dumps({"progress": 100, "message": "生成失败", "status": "error"}) + "\n\n"
            finally:
                yield "data: [DONE]\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(generate_progress(), media_type="text/event-stream")


from app.api.v1.endpoints.test_point_extract import router as extract_router
from app.api.v1.endpoints.test_point_import import router as import_router
from app.api.v1.endpoints.test_point_import_stream import router as import_stream_router

router.include_router(extract_router)
router.include_router(import_router)
router.include_router(import_stream_router)

__all__ = [
    "router",
    "check_project_permission",
    "check_project_permission_async",
]
