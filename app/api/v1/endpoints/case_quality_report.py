"""用例质量报告端点模块。

提供用例审核、编辑和待审核列表端点，以及项目/用例成本统计端点
（成本统计原先拆在 _case_quality_cost_routes.py，已合并回本文件）。

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
import asyncio
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from loguru import logger

from app.db.database import PrimarySessionLocal, get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.test_case import TestCase, TestStep
from app.api.v1.endpoints.case_quality_check import (
    CaseReviewRequest,
    CaseEditRequest,
    StepEditRequest,
)
from app.services.cost_statistics_service import CostStatisticsService
from app.utils.db_time import utcnow

router = APIRouter()


@router.post("/cases/{case_id}/review")
async def review_case(
    case_id: int,
    request: CaseReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    valid_statuses = ["pending", "approved", "rejected", "needs_optimization"]
    if request.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效的状态值，可选值: {valid_statuses}")

    try:
        result = await asyncio.to_thread(
            db.execute,
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            ),
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

        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, test_case)

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
        await asyncio.to_thread(db.rollback)
        logger.error(f"审核用例失败 {case_id}: {e}")
        raise HTTPException(status_code=500, detail="审核失败")


@router.get("/cases/{case_id}/review")
async def get_case_review_status(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await asyncio.to_thread(
            db.execute,
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            ),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        offset = (page - 1) * page_size
        base_filter = (
            TestCase.project_id == project_id,
            TestCase.review_status.in_(["pending", "needs_optimization"]),
            TestCase.is_deleted.is_(False)
        )

        count_result = await asyncio.to_thread(
            db.execute,
            select(func.count()).select_from(TestCase).where(*base_filter),
        )
        total_count = count_result.scalar() or 0

        cases_result = await asyncio.to_thread(
            db.execute,
            select(TestCase).where(*base_filter).offset(offset).limit(page_size),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        result = await asyncio.to_thread(
            db.execute,
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            ),
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
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, test_case)

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
        await asyncio.to_thread(db.rollback)
        logger.error(f"编辑用例失败 {case_id}: {e}")
        raise HTTPException(status_code=500, detail="编辑失败")


@router.put("/cases/{case_id}/steps/{step_id}")
async def edit_case_step(
    case_id: int,
    step_id: int,
    request: StepEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        case_result = await asyncio.to_thread(
            db.execute,
            select(TestCase).where(
                TestCase.id == case_id, TestCase.is_deleted.is_(False)
            ),
        )
        test_case = case_result.scalars().first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")

        step_result = await asyncio.to_thread(
            db.execute,
            select(TestStep).where(
                TestStep.id == step_id,
                TestStep.test_case_id == case_id
            ),
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

        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, step)

        logger.info(f"用例 {case_id} 步骤 {step_id} 已编辑")

        return {
            "case_id": case_id,
            "step_id": step_id,
            "message": "步骤更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        await asyncio.to_thread(db.rollback)
        logger.error(f"编辑步骤失败 {case_id}/{step_id}: {e}")
        raise HTTPException(status_code=500, detail="编辑失败")


async def _run_cost_service(fn):
    """在独立线程中执行 sync CostStatisticsService 方法，释放事件循环。

    使用 PrimarySessionLocal 创建独立 sync 会话，避免与请求级会话的事务边界互相干扰
    （成本服务内部自行 commit，不与端点事务共享）。
    """
    sync_db = PrimarySessionLocal()
    try:
        return await asyncio.to_thread(fn, sync_db)
    finally:
        sync_db.close()


@router.get("/projects/{project_id}/cost-statistics")
async def get_project_cost_statistics(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        def _do_get_summary(sync_db):
            service = CostStatisticsService(sync_db)
            return service.get_cost_summary(project_id)

        summary = await _run_cost_service(_do_get_summary)
        return summary
    except Exception as e:
        logger.error(f"获取成本统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取成本统计失败")


@router.get("/projects/{project_id}/cost-report")
async def get_project_cost_report(
    project_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        end_date = utcnow()
        start_date = end_date - timedelta(days=days)

        def _do_gen_report(sync_db):
            service = CostStatisticsService(sync_db)
            return service.generate_cost_report(project_id, start_date, end_date)

        report = await _run_cost_service(_do_gen_report)

        return {
            "report_id": report.report_id,
            "project_id": report.project_id,
            "start_date": report.start_date.isoformat(),
            "end_date": report.end_date.isoformat(),
            "overall_statistics": {
                "total_steps": report.overall_statistics.total_steps,
                "ai_vision_calls": report.overall_statistics.ai_vision_calls,
                "cache_hits": report.overall_statistics.cache_hits,
                "css_selector_used": report.overall_statistics.css_selector_used,
                "xpath_used": report.overall_statistics.xpath_used,
                "estimated_cost": report.overall_statistics.estimated_cost,
                "actual_cost": report.overall_statistics.actual_cost,
                "cost_savings": report.overall_statistics.cost_savings,
                "savings_rate": report.overall_statistics.savings_rate,
                "cache_hit_rate": report.overall_statistics.cache_hit_rate,
                "ai_dependency_rate": report.overall_statistics.ai_dependency_rate
            },
            "case_statistics": report.case_statistics,
            "daily_statistics": report.daily_statistics,
            "optimization_suggestions": report.optimization_suggestions,
            "trend_data": report.trend_data,
            "generated_at": report.generated_at.isoformat()
        }
    except Exception as e:
        logger.error(f"生成成本报表失败: {e}")
        raise HTTPException(status_code=500, detail="生成成本报表失败")


@router.get("/cases/{case_id}/cost-statistics")
async def get_case_cost_statistics(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        def _do_get_case_stats(sync_db):
            service = CostStatisticsService(sync_db)
            return service.get_case_cost_statistics(case_id)

        stats = await _run_cost_service(_do_get_case_stats)
        return {
            "case_id": case_id,
            "total_steps": stats.total_steps,
            "ai_vision_calls": stats.ai_vision_calls,
            "cache_hits": stats.cache_hits,
            "css_selector_used": stats.css_selector_used,
            "xpath_used": stats.xpath_used,
            "estimated_cost": stats.estimated_cost,
            "actual_cost": stats.actual_cost,
            "cost_savings": stats.cost_savings,
            "savings_rate": stats.savings_rate,
            "cache_hit_rate": stats.cache_hit_rate,
            "ai_dependency_rate": stats.ai_dependency_rate
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取成本统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取成本统计失败")
