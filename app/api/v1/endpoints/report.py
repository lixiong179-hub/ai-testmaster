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
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.schemas.test_report import TestReportResponse, TestReportList, ReportGenerateRequest, ReportExportRequest
from app.crud.test_report import get_test_reports, get_test_report_by_id, delete_test_report as crud_delete_report
from app.services.report_service import ReportService
from app.utils.report_utils import ReportUtils
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.project import Project
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
    def _generate(sync_db: Session):
        project = sync_db.query(Project).filter(
            Project.id == request.project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        report = ReportService.generate_report(
            db=sync_db,
            project_id=request.project_id,
            test_task_id=request.test_task_id,
            name=request.name,
            description=request.description
        )
        return report

    try:
        return await db.run_sync(_generate)
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
    def _list(sync_db: Session):
        from app.models.report import TestReport as TestReportModel

        # 多项目隔离：查询时根据project_id过滤，如果不传则查询用户所有项目的报告
        if project_id:
            reports = get_test_reports(sync_db, project_id, skip=(page-1)*page_size, limit=page_size)
            total = len(get_test_reports(sync_db, project_id))
        else:
            user_projects = sync_db.query(Project.id).filter(Project.user_id == current_user.id).all()
            project_ids = [p.id for p in user_projects]

            if project_ids:
                reports = sync_db.query(TestReportModel).filter(
                    TestReportModel.project_id.in_(project_ids)
                ).offset((page-1)*page_size).limit(page_size).all()
                total = sync_db.query(TestReportModel).filter(
                    TestReportModel.project_id.in_(project_ids)
                ).count()
            else:
                reports = []
                total = 0

        return TestReportList(
            reports=[TestReportResponse.model_validate(report) for report in reports],
            total=total
        )

    try:
        return await db.run_sync(_list)
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
    def _detail(sync_db: Session):
        project = sync_db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 多项目隔离：查询时必带project_id过滤
        report = get_test_report_by_id(sync_db, report_id, project_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试报告不存在"
            )
        return TestReportResponse.model_validate(report)

    return await db.run_sync(_detail)

@router.post("/{report_id}/export")
async def export_test_report(
    report_id: int,
    request: ReportExportRequest,
    project_id: int = Query(..., description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """导出测试报告"""
    def _prepare(sync_db: Session):
        project = sync_db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 多项目隔离：导出时必带project_id过滤
        report = get_test_report_by_id(sync_db, report_id, project_id)
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
        return report

    report = await db.run_sync(_prepare)

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
    def _delete(sync_db: Session):
        project = sync_db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 多项目隔离：删除时必带project_id过滤
        success = crud_delete_report(sync_db, report_id, project_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试报告不存在"
            )

    await db.run_sync(_delete)
    return {"message": "测试报告删除成功"}
