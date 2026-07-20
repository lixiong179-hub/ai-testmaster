"""
测试报告端点模块

本模块定义测试报告的API端点，提供测试执行结果的汇总报告和详细报告。

路由前缀: /report
标签: 测试报告

端点概览:
    - GET  /project/{project_id}/summary     - 获取项目测试汇总报告
    - GET  /project/{project_id}/detail      - 获取项目测试详细报告
    - GET  /execution/{execution_id}/report  - 获取单次执行报告

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 汇总报告包含通过率、用例分布、执行耗时等统计
    - 详细报告包含每个用例的执行步骤和结果
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.schemas.test_report import TestReportResponse, TestReportList, ReportGenerateRequest, ReportExportRequest
from app.services.report_service import ReportService
from app.utils.report_utils import ReportUtils
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.report import TestReport
from typing import Optional
from loguru import logger

router = APIRouter(prefix="/report", tags=["测试报告管理"])

@router.post("/generate", response_model=TestReportResponse)
async def generate_test_report(
    request: ReportGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """生成测试报告"""
    import asyncio
    from app.db.database import PrimarySessionLocal

    # async 权限校验
    project_result = await db.execute(
        select(Project).where(
            Project.id == request.project_id,
            Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    # ReportService.generate_report 是 sync 写操作，使用独立 sync 会话 + to_thread 释放事件循环
    def _do_generate(sync_db):
        return ReportService.generate_report(
            db=sync_db,
            project_id=request.project_id,
            test_task_id=request.test_task_id,
            name=request.name,
            description=request.description
        )

    try:
        sync_db = PrimarySessionLocal()
        try:
            return await asyncio.to_thread(_do_generate, sync_db)
        finally:
            sync_db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成报告失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成报告失败"
        )

@router.get("/", response_model=TestReportList)
async def get_test_reports_list(
    project_id: Optional[int] = Query(None, description="项目ID，不传则返回所有报告"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试报告列表"""
    try:
        # 多项目隔离：查询时根据project_id过滤，如果不传则查询用户所有项目的报告
        if project_id:
            reports_result = await db.execute(
                select(TestReport).where(TestReport.project_id == project_id)
                .offset((page - 1) * page_size).limit(page_size)
            )
            reports = reports_result.scalars().all()
            total_result = await db.execute(
                select(func.count()).select_from(TestReport)
                .where(TestReport.project_id == project_id)
            )
            total = total_result.scalar() or 0
        else:
            user_projects_result = await db.execute(
                select(Project.id).where(Project.user_id == current_user.id)
            )
            project_ids = list(user_projects_result.scalars().all())

            if project_ids:
                reports_result = await db.execute(
                    select(TestReport).where(TestReport.project_id.in_(project_ids))
                    .offset((page - 1) * page_size).limit(page_size)
                )
                reports = reports_result.scalars().all()
                total_result = await db.execute(
                    select(func.count()).select_from(TestReport)
                    .where(TestReport.project_id.in_(project_ids))
                )
                total = total_result.scalar() or 0
            else:
                reports = []
                total = 0

        return TestReportList(
            reports=[TestReportResponse.model_validate(report) for report in reports],
            total=total
        )
    except Exception:
        # 兜底逻辑：返回空列表
        return TestReportList(
            reports=[],
            total=0
        )

@router.get("/{report_id}", response_model=TestReportResponse)
async def get_test_report_detail(
    report_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试报告详情"""
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    # 多项目隔离：查询时必带project_id过滤
    report_result = await db.execute(
        select(TestReport).where(
            TestReport.id == report_id,
            TestReport.project_id == project_id
        )
    )
    report = report_result.scalars().first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在"
        )
    return TestReportResponse.model_validate(report)

@router.post("/{report_id}/export")
async def export_test_report(
    report_id: int,
    request: ReportExportRequest,
    project_id: int = Query(..., description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """导出测试报告"""
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    # 多项目隔离：导出时必带project_id过滤
    report_result = await db.execute(
        select(TestReport).where(
            TestReport.id == report_id,
            TestReport.project_id == project_id
        )
    )
    report = report_result.scalars().first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在"
        )

    if not report.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="报告内容为空，无法导出"
        )

    try:
        # 导出报告
        content, content_type, filename = ReportUtils.export_report(
            report_data=report.content,
            report_name=report.name,
            format=request.format
        )

        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except HTTPException:
        raise
    except Exception:
        logger.error("导出报告失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出报告失败"
        )

@router.delete("/{report_id}")
async def delete_test_report(
    report_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """删除测试报告"""
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    # 多项目隔离：删除时必带project_id过滤
    report_result = await db.execute(
        select(TestReport).where(
            TestReport.id == report_id,
            TestReport.project_id == project_id
        )
    )
    report = report_result.scalars().first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试报告不存在"
        )

    await db.delete(report)
    await db.commit()
    return {"message": "测试报告删除成功"}
