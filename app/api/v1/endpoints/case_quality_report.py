"""用例质量报告端点模块。

提供用例审核、编辑和待审核列表端点。
成本统计端点已拆分至 _case_quality_cost_routes。

路由前缀: /quality（由父模块 case_quality.py 注册）
标签: 用例质量

端点概览:
    - POST /cases/{case_id}/review                - 审核用例
    - GET  /cases/{case_id}/review                 - 获取用例审核状态
    - GET  /projects/{project_id}/pending-reviews  - 获取待审核用例列表
    - PUT  /cases/{case_id}/edit                   - 编辑用例
    - PUT  /cases/{case_id}/steps/{step_id}        - 编辑用例步骤
    - GET  /projects/{project_id}/cost-statistics  - 成本统计（拆分模块）
    - GET  /projects/{project_id}/cost-report      - 成本报表（拆分模块）
    - GET  /cases/{case_id}/cost-statistics        - 用例成本统计（拆分模块）

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.database import async_get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.test_case import TestCase, TestStep
from app.api.v1.endpoints.case_quality_check import (
    CaseReviewRequest,
    CaseEditRequest,
    StepEditRequest,
)
from app.api.v1.endpoints._case_quality_cost_routes import router as cost_router
from app.utils.db_time import utcnow

router = APIRouter()
router.include_router(cost_router)


@router.post("/cases/{case_id}/review")
async def review_case(
    case_id: int,
    request: CaseReviewRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    valid_statuses = ["pending", "approved", "rejected", "needs_optimization"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效的状态值，可选值: {valid_statuses}")

    try:
        result = await db.execute(
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            )
        )
        test_case = result.scalars().first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")

        test_case.review_status = request.status
        test_case.review_comment = request.review_comment
        test_case.reviewed_by = current_user.username if current_user else None
        test_case.reviewed_at = utcnow()
        if request.priority:
            test_case.priority = request.priority

        await db.commit()
        await db.refresh(test_case)

        logger.info(f"用例 {case_id} 审核状态更新为: {request.status}, 审核人: {current_user.username if current_user else 'unknown'}")

        return {
            "case_id": case_id,
            "status": test_case.review_status,
            "review_comment": test_case.review_comment,
            "reviewed_by": test_case.reviewed_by,
            "reviewed_at": test_case.reviewed_at.isoformat() if test_case.reviewed_at else None,
            "priority": test_case.priority
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"审核用例失败 {case_id}: {e}")
        raise HTTPException(status_code=500, detail="审核失败")


@router.get("/cases/{case_id}/review")
async def get_case_review_status(
    case_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            )
        )
        test_case = result.scalars().first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")

        return {
            "case_id": case_id,
            "case_name": test_case.title,
            "status": getattr(test_case, 'review_status', 'pending'),
            "review_comment": getattr(test_case, 'review_comment', None),
            "reviewed_by": getattr(test_case, 'reviewed_by', None),
            "reviewed_at": getattr(test_case, 'reviewed_at', None),
            "priority": getattr(test_case, 'priority', 'medium')
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用例审核状态失败 {case_id}: {e}")
        raise HTTPException(status_code=500, detail="获取审核状态失败")


@router.get("/projects/{project_id}/pending-reviews")
async def get_pending_reviews(
    project_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        offset = (page - 1) * page_size
        base_filter = (
            TestCase.project_id == project_id,
            TestCase.review_status.in_(["pending", "needs_optimization"]),
            TestCase.is_deleted.is_(False)
        )

        count_result = await db.execute(
            select(func.count()).select_from(TestCase).where(*base_filter)
        )
        total_count = count_result.scalar() or 0

        cases_result = await db.execute(
            select(TestCase).where(*base_filter).offset(offset).limit(page_size)
        )
        cases = cases_result.scalars().all()

        total_pages = (total_count + page_size - 1) // page_size

        return {
            "project_id": project_id,
            "pending_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "cases": [
                {
                    "case_id": case.id,
                    "case_name": case.title,
                    "status": getattr(case, 'review_status', 'pending'),
                    "priority": getattr(case, 'priority', 'medium'),
                    "create_time": case.create_time.isoformat() if hasattr(case, 'create_time') and case.create_time else None
                }
                for case in cases
            ]
        }
    except Exception as e:
        logger.error(f"获取待审核用例列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取待审核列表失败")


@router.put("/cases/{case_id}/edit")
async def edit_case(
    case_id: int,
    request: CaseEditRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            )
        )
        test_case = result.scalars().first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")

        if request.title:
            test_case.title = request.title
        if request.description:
            test_case.expected_result = request.description
        if request.preconditions:
            test_case.precondition = request.preconditions
        if request.expected_result:
            test_case.expected_result = request.expected_result
        if request.priority:
            test_case.priority = request.priority

        test_case.update_time = utcnow()
        await db.commit()
        await db.refresh(test_case)

        logger.info(f"用例 {case_id} 已编辑, 操作人: {current_user.username if current_user else 'unknown'}")

        return {
            "case_id": case_id,
            "message": "用例更新成功",
            "updated_fields": {
                "title": request.title,
                "description": request.description,
                "preconditions": request.preconditions,
                "expected_result": request.expected_result,
                "priority": request.priority
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"编辑用例失败 {case_id}: {e}")
        raise HTTPException(status_code=500, detail="编辑失败")


@router.put("/cases/{case_id}/steps/{step_id}")
async def edit_case_step(
    case_id: int,
    step_id: int,
    request: StepEditRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        case_result = await db.execute(
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            )
        )
        test_case = case_result.scalars().first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")

        step_result = await db.execute(
            select(TestStep).where(
                TestStep.id == step_id,
                TestStep.test_case_id == case_id
            )
        )
        step = step_result.scalars().first()

        if not step:
            raise HTTPException(status_code=404, detail="步骤不存在")

        if request.action:
            step.action = request.action
        if request.target:
            step.target_element = request.target
        if request.value:
            step.input_value = request.value
        if request.expected_result:
            step.expected_result = request.expected_result

        await db.commit()
        await db.refresh(step)

        logger.info(f"用例 {case_id} 步骤 {step_id} 已编辑")

        return {
            "case_id": case_id,
            "step_id": step_id,
            "message": "步骤更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"编辑步骤失败 {case_id}/{step_id}: {e}")
        raise HTTPException(status_code=500, detail="编辑失败")
