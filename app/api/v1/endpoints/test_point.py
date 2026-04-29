"""测试点管理模块

本模块为测试点核心管理功能，包含查询、变更、独立管理等端点。
提取相关端点（文件提取/UI原型提取/XMind导入）在 test_point_extract.py 中定义。

路由前缀: /test-point
标签: 测试点管理

端点概览:
    - POST /analyze                      - 分析项目（SSE流式）
    - GET  /list/{project_id}            - 获取测试点列表
    - GET  /detail/{test_point_id}       - 获取测试点详情
    - POST /batch-save                   - 批量保存测试点
    - PUT  /{test_point_id}              - 更新测试点
    - DELETE /batch                      - 批量删除测试点
    - DELETE /{test_point_id}            - 删除测试点
    - POST /                             - 创建单个测试点
    - GET  /{test_point_id}/test-cases   - 查询关联用例
    - GET  /requirements/{project_id}    - 获取需求筛选选项
    - POST /batch-generate-cases/stream  - 批量流式生成用例

所有端点均需要Bearer令牌认证。
"""
import json
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.crud.test_point import (
    batch_create_test_points,
    create_test_point,
    get_test_point_by_id,
)
from app.crud.test_point_management import (
    get_requirements_by_project,
    get_test_cases_by_test_point,
    get_test_cases_by_test_point_total,
    get_test_point_list_stats,
    get_test_points_with_case_count,
    get_test_points_with_case_count_total,
)
from app.db.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.test_point import (
    TestPointAnalyzeRequest,
    TestPointBatchGenerateRequest,
    TestPointCreate,
    TestPointRelatedCaseResponse,
    TestPointRequirementOptionResponse,
    TestPointResponse,
    TestPointUpdate,
)
from app.services.ai_analysis_service import aio_analysis_service
from app.services.test_case_generation_service import TestCaseGenerationService

router = APIRouter(prefix="/test-point", tags=["测试点管理"])


def check_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    """校验用户对项目的操作权限，无权限时抛出403。"""
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    return project


# ── 查询端点 ──────────────────────────────────────────────


@router.post("/analyze")
async def analyze_project(
    request: TestPointAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分析项目，以SSE流式返回分析进度。"""
    try:
        async def generate_progress() -> Any:
            async for progress in aio_analysis_service.analyze_project(
                db=db, project_id=request.project_id,
                user_id=current_user.id, username=current_user.username,
            ):
                yield f"data: {json.dumps(progress)}\n\n"

        return StreamingResponse(generate_progress(), media_type="text/event-stream")
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取测试点列表（分页），含统计信息。"""
    try:
        skip = (page - 1) * page_size
        test_points = get_test_points_with_case_count(
            db=db, project_id=project_id, user_id=current_user.id,
            module=module, priority=priority, created_by=created_by,
            requirement_id=requirement_id, keyword=keyword,
            created_from=created_from, created_to=created_to,
            skip=skip, limit=page_size, sort_by=sort_by, sort_order=sort_order,
        )
        total = get_test_points_with_case_count_total(
            db=db, project_id=project_id, user_id=current_user.id,
            module=module, priority=priority, created_by=created_by,
            requirement_id=requirement_id, keyword=keyword,
            created_from=created_from, created_to=created_to,
        )
        stats = get_test_point_list_stats(
            db=db, project_id=project_id, user_id=current_user.id,
            module=module, created_by=created_by,
            requirement_id=requirement_id, keyword=keyword,
            created_from=created_from, created_to=created_to,
        )
        items = [
            TestPointResponse(
                id=point.id, project_id=point.project_id,
                requirement_id=point.requirement_id, module=point.module,
                function=point.function, point=point.point,
                priority=point.priority, ai_prompt=point.ai_prompt,
                create_time=point.create_time, created_by=point.created_by,
                test_case_count=case_count,
            )
            for point, case_count in test_points
        ]
        return {
            "code": 200, "message": "获取成功",
            "data": {
                "total": total, "items": items,
                "page": page, "page_size": page_size, "stats": stats,
            },
        }
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
    """获取测试点详情。"""
    try:
        project = db.query(Project).filter(
            Project.id == project_id, Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
            )
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在"
            )
        test_case_count = get_test_cases_by_test_point_total(
            db=db, project_id=project_id,
            user_id=current_user.id, test_point_id=test_point_id,
        )
        return TestPointResponse(
            id=test_point.id, project_id=test_point.project_id,
            requirement_id=test_point.requirement_id, module=test_point.module,
            function=test_point.function, point=test_point.point,
            priority=test_point.priority, ai_prompt=test_point.ai_prompt,
            create_time=test_point.create_time, created_by=test_point.created_by,
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


# ── 变更端点 ──────────────────────────────────────────────


@router.post("/batch-save")
async def batch_save_test_points(
    project_id: int = Query(..., description="项目ID"),
    test_points: List[Dict[str, Any]] = Body(..., description="测试点列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量保存测试点，单次上限200个。"""
    max_batch_size = 200
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    try:
        if not test_points or not isinstance(test_points, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="测试点列表不能为空"
            )
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
            valid_points.append({
                "module": module, "function": item.get("function", ""),
                "point": point,
                "priority": priority, "ai_prompt": item.get("ai_prompt"),
            })
        if not valid_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点数据可保存",
            )
        saved = batch_create_test_points(
            db=db, project_id=project_id,
            test_points_data=valid_points, created_by=current_user.username,
        )
        logger.info(
            f"批量保存测试点成功: {len(saved)}/{len(valid_points)} 个 "
            f"(用户: {current_user.username})"
        )
        return {
            "code": 200,
            "message": f"成功保存 {len(saved)} 个测试点",
            "data": {
                "saved_count": len(saved), "total_submitted": len(valid_points),
                "items": [
                    {"id": tp.id, "module": tp.module,
                     "point": tp.point, "priority": tp.priority}
                    for tp in saved
                ],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量保存测试点失败: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存失败"
        )


@router.put("/{test_point_id}")
async def update_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    update_data: TestPointUpdate = Body(..., description="更新数据"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新测试点。"""
    try:
        check_project_permission(db, project_id, current_user.id)
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在"
            )
        if update_data.module is not None:
            test_point.module = update_data.module
        if update_data.function is not None:
            test_point.function = update_data.function
        if update_data.point is not None:
            test_point.point = update_data.point
        if update_data.priority is not None:
            test_point.priority = update_data.priority
        if update_data.ai_prompt is not None:
            test_point.ai_prompt = update_data.ai_prompt
        db.commit()
        db.refresh(test_point)
        logger.info(f"用户 {current_user.username} 更新了测试点 {test_point_id}")
        return {
            "code": 200, "message": "更新成功",
            "data": TestPointResponse(
                id=test_point.id, project_id=test_point.project_id,
                requirement_id=test_point.requirement_id, module=test_point.module,
                function=test_point.function, point=test_point.point,
                priority=test_point.priority, ai_prompt=test_point.ai_prompt,
                create_time=test_point.create_time, created_by=test_point.created_by,
                test_case_count=0,
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


@router.delete("/batch")
async def batch_delete_test_points(
    project_id: int = Query(..., description="项目ID"),
    ids: List[int] = Body(..., description="要删除的测试点ID列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量删除测试点，单次上限100个。"""
    max_batch_delete = 100
    try:
        check_project_permission(db, project_id, current_user.id)
        if not ids or not isinstance(ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请提供有效的ID列表"
            )
        unique_ids = list(set(filter(lambda x: isinstance(x, int) and x > 0, ids)))
        if len(unique_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="没有有效的测试点ID"
            )
        if len(unique_ids) > max_batch_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次删除数量不能超过{max_batch_delete}个（当前{len(unique_ids)}个）",
            )
        from app.models.test_point import TestPoint as TestPointModel
        deleted_count = db.query(TestPointModel).filter(
            TestPointModel.id.in_(unique_ids),
            TestPointModel.project_id == project_id,
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"用户 {current_user.username} 批量删除了 {deleted_count} 个测试点")
        return {
            "code": 200, "message": f"成功删除 {deleted_count} 个测试点",
            "data": {"deleted_count": deleted_count, "requested_count": len(unique_ids)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除测试点失败: {e}", exc_info=True)
        db.rollback()
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
    """删除单个测试点。"""
    try:
        check_project_permission(db, project_id, current_user.id)
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        if not test_point:
            return {"code": 200, "message": "删除成功", "data": {"id": test_point_id}}
        db.delete(test_point)
        db.commit()
        logger.info(f"用户 {current_user.username} 删除了测试点 {test_point_id}")
        return {"code": 200, "message": "删除成功", "data": {"id": test_point_id}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


# ── 独立管理端点 ──────────────────────────────────────────


@router.post("/", response_model=TestPointResponse)
async def create_test_point_item(
    request: TestPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestPointResponse:
    """创建单个测试点。"""
    check_project_permission(db, request.project_id, current_user.id)
    created = create_test_point(
        db=db, project_id=request.project_id, module=request.module,
        function=request.function, point=request.point, priority=request.priority,
        ai_prompt=request.ai_prompt, created_by=current_user.username,
    )
    return TestPointResponse(
        id=created.id, project_id=created.project_id,
        requirement_id=created.requirement_id, module=created.module,
        function=created.function, point=created.point,
        priority=created.priority, ai_prompt=created.ai_prompt,
        create_time=created.create_time, created_by=created.created_by,
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
    """查询测试点关联的测试用例列表。"""
    check_project_permission(db, project_id, current_user.id)
    test_point = get_test_point_by_id(db, test_point_id, project_id)
    if not test_point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在"
        )
    skip = (page - 1) * page_size
    items = get_test_cases_by_test_point(
        db=db, project_id=project_id, user_id=current_user.id,
        test_point_id=test_point_id, skip=skip, limit=page_size,
    )
    total = get_test_cases_by_test_point_total(
        db=db, project_id=project_id, user_id=current_user.id,
        test_point_id=test_point_id,
    )
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取测试点管理页的需求筛选选项。"""
    check_project_permission(db, project_id, current_user.id)
    requirements = get_requirements_by_project(
        db=db, project_id=project_id, user_id=current_user.id,
    )
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """基于测试点批量流式生成测试用例。"""
    check_project_permission(db, request.project_id, current_user.id)

    async def generate_progress() -> Any:
        service = TestCaseGenerationService(db)
        try:
            async for progress in service.generate_test_cases_batch(
                project_id=request.project_id, user_id=current_user.id,
                test_point_ids=request.test_point_ids, case_type=request.case_type,
            ):
                yield f"data: {json.dumps(progress)}\n\n"
        except Exception as exc:
            logger.error(f"测试点批量生成测试用例失败: {exc}")
            yield "data: " + json.dumps(
                {"progress": 100, "message": "生成失败", "status": "error"}
            ) + "\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate_progress(), media_type="text/event-stream")


# ── 注册提取子模块路由 ───────────────────────────────────
from app.api.v1.endpoints.test_point_extract import router as extract_router  # noqa: E402
from app.api.v1.endpoints.test_point_import import router as import_router  # noqa: E402
from app.api.v1.endpoints.test_point_import_stream import router as import_stream_router  # noqa: E402

router.include_router(extract_router)
router.include_router(import_router)
router.include_router(import_stream_router)
