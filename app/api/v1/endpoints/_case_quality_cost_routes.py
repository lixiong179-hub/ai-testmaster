"""用例质量成本统计端点（从 case_quality_report 拆分）。

包含项目成本统计、成本报表、用例成本统计 3 个端点，
CostStatisticsService 为 sync 实现，端点使用 asyncio.to_thread + PrimarySessionLocal 释放事件循环。
"""
import asyncio
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.database import async_get_db, PrimarySessionLocal
from app.api.v1.endpoints.auth import get_current_user
from app.services.cost_statistics_service import CostStatisticsService
from app.models.user import User
from app.utils.db_time import utcnow

router = APIRouter()


async def _run_cost_service(fn):
    """在独立线程中执行 sync CostStatisticsService 方法，释放事件循环。

    使用 PrimarySessionLocal 创建独立 sync 会话，避免与 AsyncSession 事务冲突。
    """
    sync_db = PrimarySessionLocal()
    try:
        return await asyncio.to_thread(fn, sync_db)
    finally:
        sync_db.close()


@router.get("/projects/{project_id}/cost-statistics")
async def get_project_cost_statistics(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
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
    db: AsyncSession = Depends(async_get_db),
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
    db: AsyncSession = Depends(async_get_db),
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
