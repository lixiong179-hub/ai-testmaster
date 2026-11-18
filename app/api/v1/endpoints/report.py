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

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_report import TestReportResponse, TestReportList, ReportGenerateRequest, ReportExportRequest
from app.services.report_service import ReportService
from app.utils.report_utils import ReportUtils
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.report import TestReport
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.test_result import TestResult
from typing import Any
import json
from loguru import logger


async def _execute(db: Session, stmt):
    """同步 Session 的查询在线程池执行，避免阻塞事件循环（R2-1）。"""
    return await asyncio.to_thread(db.execute, stmt)


router = APIRouter(prefix="/report", tags=["测试报告管理"])


@router.post("/generate", response_model=TestReportResponse)
async def generate_test_report(
    request: ReportGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """生成测试报告"""
    import asyncio
    from app.db.database import PrimarySessionLocal

    # async 权限校验
    project_result = await _execute(
        db, select(Project).where(Project.id == request.project_id, Project.user_id == current_user.id)
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

    # ReportService.generate_report 是 sync 写操作，使用独立 sync 会话 + to_thread 释放事件循环
    def _do_generate(sync_db):
        return ReportService.generate_report(
            db=sync_db,
            project_id=request.project_id,
            test_task_id=request.test_task_id,
            name=request.name,
            description=request.description,
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成报告失败")


@router.get("/", response_model=TestReportList)
async def get_test_reports_list(
    project_id: int | None = Query(None, description="项目ID，不传则返回所有报告"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取测试报告列表"""
    try:
        # 多项目隔离：查询时根据project_id过滤，如果不传则查询用户所有项目的报告
        if project_id:
            reports_result = await _execute(
                db,
                select(TestReport)
                .where(TestReport.project_id == project_id)
                .offset((page - 1) * page_size)
                .limit(page_size),
            )
            reports = reports_result.scalars().all()
            total_result = await _execute(
                db, select(func.count()).select_from(TestReport).where(TestReport.project_id == project_id)
            )
            total = total_result.scalar() or 0
        else:
            user_projects_result = await _execute(db, select(Project.id).where(Project.user_id == current_user.id))
            project_ids = list(user_projects_result.scalars().all())

            if project_ids:
                reports_result = await _execute(
                    db,
                    select(TestReport)
                    .where(TestReport.project_id.in_(project_ids))
                    .offset((page - 1) * page_size)
                    .limit(page_size),
                )
                reports = reports_result.scalars().all()
                total_result = await _execute(
                    db, select(func.count()).select_from(TestReport).where(TestReport.project_id.in_(project_ids))
                )
                total = total_result.scalar() or 0
            else:
                reports = []
                total = 0

        return TestReportList(reports=[TestReportResponse.model_validate(report) for report in reports], total=total)
    except Exception:
        # 兜底逻辑：返回空列表
        return TestReportList(reports=[], total=0)


def _extract_final_answer(content: Any) -> str | None:
    """从 Agent 的 final_answer 消息内容提取结论文本（截断 500 字符）。"""
    data = content
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data[:500]
    if not isinstance(data, dict):
        return None

    arguments = data.get("arguments")
    if isinstance(arguments, str):
        try:
            data = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            return arguments[:500]
    if not isinstance(data, dict):
        return None

    for key in ("conclusion", "summary", "final_answer", "visual_result"):
        value = data.get(key)
        if not value:
            continue
        return value if isinstance(value, str) else str(value)[:500]
    return json.dumps(data, ensure_ascii=False)[:500]


async def _load_visual_validation_summary(db: Session, project_id: int) -> dict | None:
    """汇总最近一次视觉校验会话的结论与截图引用（R3-3）。

    数据来源：`agent_sessions`（agent_type=visual_validation）+
    `agent_messages`（tool_name=final_answer）+ 最近一次执行结果截图。
    未启用视觉校验的项目不存在会话，返回 None（报告无该区块）。
    """
    try:
        session = (
            (
                await _execute(
                    db,
                    select(AgentSession)
                    .where(
                        AgentSession.project_id == project_id,
                        AgentSession.agent_type == "visual_validation",
                    )
                    .order_by(AgentSession.id.desc())
                    .limit(1),
                )
            )
            .scalars()
            .first()
        )
        if session is None:
            return None

        message = (
            (
                await _execute(
                    db,
                    select(AgentMessage)
                    .where(
                        AgentMessage.session_id == session.id,
                        AgentMessage.tool_name == "final_answer",
                    )
                    .order_by(AgentMessage.id.desc())
                    .limit(1),
                )
            )
            .scalars()
            .first()
        )
        conclusion = _extract_final_answer(message.content) if message else None

        screenshot_url = (
            await _execute(
                db,
                select(TestResult.screenshot_url)
                .where(
                    TestResult.project_id == project_id,
                    TestResult.screenshot_url.isnot(None),
                )
                .order_by(TestResult.id.desc())
                .limit(1),
            )
        ).scalar_one_or_none()

        checked_at = session.completed_at or session.started_at
        return {
            "session_id": session.id,
            "status": session.status,
            "conclusion": conclusion,
            "screenshot_url": screenshot_url,
            "checked_at": checked_at.isoformat() if checked_at else None,
            "token_cost": session.token_cost,
            "iterations": session.iteration_count,
        }
    except Exception as exc:
        # 报告主体可用性优先：视觉校验区块异常仅告警
        logger.warning(f"汇总视觉校验结论失败（不影响报告输出）: {exc}")
        return None


async def _attach_visual_validation(db: Session, report: TestReport) -> TestReportResponse:
    """在报告详情中附加视觉校验结论与截图引用。"""
    data = TestReportResponse.model_validate(report)
    summary = await _load_visual_validation_summary(db, report.project_id)
    if summary:
        content = dict(data.content or {})
        content["visual_validation"] = summary
        data.content = content
    return data


@router.get("/{report_id}", response_model=TestReportResponse)
async def get_test_report_detail(
    report_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取测试报告详情"""
    project_result = await _execute(
        db, select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

    # 多项目隔离：查询时必带project_id过滤
    report_result = await _execute(
        db, select(TestReport).where(TestReport.id == report_id, TestReport.project_id == project_id)
    )
    report = report_result.scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试报告不存在")
    return await _attach_visual_validation(db, report)


@router.post("/{report_id}/export")
async def export_test_report(
    report_id: int,
    request: ReportExportRequest,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出测试报告"""
    project_result = await _execute(
        db, select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

    # 多项目隔离：导出时必带project_id过滤
    report_result = await _execute(
        db, select(TestReport).where(TestReport.id == report_id, TestReport.project_id == project_id)
    )
    report = report_result.scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试报告不存在")

    if not report.content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="报告内容为空，无法导出")

    try:
        # 导出报告
        content, content_type, filename = ReportUtils.export_report(
            report_data=report.content, report_name=report.name, format=request.format
        )

        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HTTPException:
        raise
    except Exception:
        logger.error("导出报告失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="导出报告失败")


@router.delete("/{report_id}")
async def delete_test_report(
    report_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除测试报告"""
    project_result = await _execute(
        db, select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = project_result.scalars().first()

    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")

    # 多项目隔离：删除时必带project_id过滤
    report_result = await _execute(
        db, select(TestReport).where(TestReport.id == report_id, TestReport.project_id == project_id)
    )
    report = report_result.scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试报告不存在")

    await asyncio.to_thread(db.delete, report)
    await asyncio.to_thread(db.commit)
    return {"message": "测试报告删除成功"}
