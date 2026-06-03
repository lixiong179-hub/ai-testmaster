"""Bug缺陷管理API端点模块

本模块定义Bug缺陷的列表查询API端点，支持按项目、严重程度、
来源、UX分类等维度筛选。

路由前缀: /bugs（由 main.py 注册）
标签: Bug缺陷管理

端点概览:
    - GET /list - 获取Bug列表（分页，支持ux_category筛选）

权限要求: 所有端点需要Bearer令牌认证
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.models.bug import Bug, VALID_UX_CATEGORIES
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.core.exception import create_response

router = APIRouter()


@router.get("/list", response_model=dict)
async def list_bugs(
    project_id: int = Query(..., description="项目ID"),
    severity: Optional[int] = Query(None, ge=1, le=4, description="严重程度: 1致命/2严重/3一般/4轻微"),
    source: Optional[str] = Query(None, description="Bug来源: manual/self_test"),
    ux_category: Optional[str] = Query(None, description="UX缺陷分类"),
    status_filter: Optional[str] = Query(None, alias="status", description="状态: open/in_progress/fixed/closed/rejected"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取Bug列表，支持多维度筛选。

    支持按项目ID（必填）、严重程度、来源、UX分类、状态筛选，
    并按创建时间倒序分页返回。

    Args:
        project_id: 项目ID（必填）。
        severity: 严重程度筛选（1-4）。
        source: Bug来源筛选（manual/self_test）。
        ux_category: UX缺陷分类筛选。
        status_filter: 状态筛选。
        page: 页码。
        page_size: 每页数量。
        db: 数据库会话。
        current_user: 当前认证用户。

    Returns:
        包含 items 和 total 的分页结果。
    """
    # 校验项目存在
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目不存在: {project_id}",
        )

    # 校验 ux_category 合法性
    if ux_category is not None and ux_category not in VALID_UX_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ux_category 不合法，可选值: {', '.join(sorted(VALID_UX_CATEGORIES))}",
        )

    # 构建查询
    query = db.query(Bug).filter(Bug.project_id == project_id)

    if severity is not None:
        query = query.filter(Bug.severity == severity)
    if source is not None:
        query = query.filter(Bug.source == source)
    if ux_category is not None:
        query = query.filter(Bug.ux_category == ux_category)
    if status_filter is not None:
        query = query.filter(Bug.status == status_filter)

    # 按创建时间倒序
    query = query.order_by(Bug.create_time.desc())

    # 分页
    total = query.count()
    offset = (page - 1) * page_size
    bugs = query.offset(offset).limit(page_size).all()

    items = [
        {
            "id": bug.id,
            "bug_no": bug.bug_no,
            "title": bug.title,
            "severity": bug.severity,
            "priority": bug.priority,
            "status": bug.status,
            "source": bug.source,
            "ux_category": bug.ux_category,
            "reporter_id": bug.reporter_id,
            "assignee_id": bug.assignee_id,
            "test_case_id": bug.test_case_id,
            "test_result_id": bug.test_result_id,
            "create_time": bug.create_time.isoformat() if bug.create_time else None,
            "update_time": bug.update_time.isoformat() if bug.update_time else None,
        }
        for bug in bugs
    ]

    return create_response(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    })
