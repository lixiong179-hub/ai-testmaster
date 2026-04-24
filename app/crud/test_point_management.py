"""
测试点独立管理查询模块

为测试点独立管理页提供增强查询能力，包括：
1. 多条件筛选 + 排序 + 分页
2. 关联测试用例数量聚合
3. 测试点关联用例列表查询
"""
from datetime import date, datetime, time
from typing import List, Optional, Tuple

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_point import TestPoint

SORT_FIELD_MAP = {
    "create_time": TestPoint.create_time,
    "priority": TestPoint.priority,
    "module": TestPoint.module,
    "function": TestPoint.function,
}


def _build_test_point_filters(
    query,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
    keyword: Optional[str] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
    apply_priority: bool = True,
):
    """构建测试点管理页的通用筛选条件。"""
    query = query.join(Project, Project.id == TestPoint.project_id).filter(
        TestPoint.project_id == project_id,
        Project.user_id == user_id,
    )

    if module:
        query = query.filter(TestPoint.module == module)
    if apply_priority and priority is not None:
        query = query.filter(TestPoint.priority == priority)
    if created_by:
        query = query.filter(TestPoint.created_by == created_by)
    if requirement_id is not None:
        query = query.filter(TestPoint.requirement_id == requirement_id)
    if keyword:
        keyword_like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                TestPoint.module.ilike(keyword_like),
                TestPoint.function.ilike(keyword_like),
                TestPoint.point.ilike(keyword_like),
            )
        )
    if created_from:
        query = query.filter(
            TestPoint.create_time >= datetime.combine(created_from, time.min)
        )
    if created_to:
        query = query.filter(
            TestPoint.create_time <= datetime.combine(created_to, time.max)
        )
    return query


def get_test_points_with_case_count(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
    keyword: Optional[str] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "create_time",
    sort_order: str = "desc",
) -> List[Tuple[TestPoint, int]]:
    """获取带关联用例数量的测试点列表。"""
    case_count_subquery = (
        db.query(
            TestCase.test_point_id.label("test_point_id"),
            func.count(TestCase.id).label("test_case_count"),
        )
        .filter(
            TestCase.project_id == project_id,
            TestCase.test_point_id.isnot(None),
            TestCase.is_deleted.is_(False),
        )
        .group_by(TestCase.test_point_id)
        .subquery()
    )

    query = db.query(
        TestPoint,
        func.coalesce(case_count_subquery.c.test_case_count, 0).label("test_case_count"),
    ).outerjoin(
        case_count_subquery,
        case_count_subquery.c.test_point_id == TestPoint.id,
    )

    query = _build_test_point_filters(
        query=query,
        project_id=project_id,
        user_id=user_id,
        module=module,
        priority=priority,
        created_by=created_by,
        requirement_id=requirement_id,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
    )

    sort_column = SORT_FIELD_MAP.get(sort_by, TestPoint.create_time)
    order_by_clause = asc(sort_column) if sort_order == "asc" else desc(sort_column)
    query = query.order_by(order_by_clause, desc(TestPoint.id))

    return query.offset(skip).limit(limit).all()


def get_test_points_with_case_count_total(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
    keyword: Optional[str] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
) -> int:
    """获取增强筛选后的测试点总数。"""
    query = db.query(func.count(TestPoint.id))
    query = _build_test_point_filters(
        query=query,
        project_id=project_id,
        user_id=user_id,
        module=module,
        priority=priority,
        created_by=created_by,
        requirement_id=requirement_id,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
    )
    return query.scalar() or 0


def get_test_point_list_stats(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
    keyword: Optional[str] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
) -> dict:
    """获取测试点列表的全局统计信息。

    统计会忽略当前优先级筛选，以便前端卡片可以作为优先级切换入口。
    """
    case_count_subquery = (
        db.query(
            TestCase.test_point_id.label("test_point_id"),
            func.count(TestCase.id).label("test_case_count"),
        )
        .filter(
            TestCase.project_id == project_id,
            TestCase.test_point_id.isnot(None),
            TestCase.is_deleted.is_(False),
        )
        .group_by(TestCase.test_point_id)
        .subquery()
    )

    query = db.query(
        TestPoint.priority,
        func.coalesce(case_count_subquery.c.test_case_count, 0).label("test_case_count"),
    ).outerjoin(
        case_count_subquery,
        case_count_subquery.c.test_point_id == TestPoint.id,
    )

    query = _build_test_point_filters(
        query=query,
        project_id=project_id,
        user_id=user_id,
        module=module,
        priority=None,
        created_by=created_by,
        requirement_id=requirement_id,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
        apply_priority=False,
    )

    stats = {
        "total": 0,
        "high_priority_count": 0,
        "medium_priority_count": 0,
        "low_priority_count": 0,
        "generated_case_count": 0,
    }
    for priority_value, test_case_count in query.all():
        stats["total"] += 1
        stats["generated_case_count"] += int(test_case_count or 0)
        if priority_value == 1:
            stats["high_priority_count"] += 1
        elif priority_value == 2:
            stats["medium_priority_count"] += 1
        elif priority_value == 3:
            stats["low_priority_count"] += 1
    return stats


def get_requirements_by_project(
    db: Session,
    project_id: int,
    user_id: int,
) -> List[Requirement]:
    """获取项目下可供测试点筛选使用的需求列表。"""
    return (
        db.query(Requirement)
        .join(Project, Project.id == Requirement.project_id)
        .filter(
            Requirement.project_id == project_id,
            Project.user_id == user_id,
        )
        .order_by(desc(Requirement.create_time), desc(Requirement.id))
        .all()
    )


def get_test_cases_by_test_point(
    db: Session,
    project_id: int,
    user_id: int,
    test_point_id: int,
    skip: int = 0,
    limit: int = 100,
) -> List[TestCase]:
    """获取测试点关联的测试用例列表。"""
    return (
        db.query(TestCase)
        .join(Project, Project.id == TestCase.project_id)
        .filter(
            TestCase.project_id == project_id,
            TestCase.test_point_id == test_point_id,
            TestCase.is_deleted.is_(False),
            Project.user_id == user_id,
        )
        .order_by(desc(TestCase.create_time), desc(TestCase.id))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_test_cases_by_test_point_total(
    db: Session,
    project_id: int,
    user_id: int,
    test_point_id: int,
) -> int:
    """获取测试点关联用例总数。"""
    return (
        db.query(func.count(TestCase.id))
        .join(Project, Project.id == TestCase.project_id)
        .filter(
            TestCase.project_id == project_id,
            TestCase.test_point_id == test_point_id,
            TestCase.is_deleted.is_(False),
            Project.user_id == user_id,
        )
        .scalar()
        or 0
    )
