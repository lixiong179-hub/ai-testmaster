"""测试点独立管理异步查询模块。

从 `app/crud/test_point_management.py` 拆分而来，集中存放 AsyncSession 版本
的增强查询函数，避免单文件超过 350 行。sync 版本仍保留在原文件中。

函数清单：
    - get_test_points_with_case_count_async: 获取带关联用例数量的测试点列表（异步）
    - get_test_points_with_case_count_total_async: 获取增强筛选后的测试点总数（异步）
    - get_test_point_list_stats_async: 获取测试点列表全局统计信息（异步）

设计说明：
    原 sync 版本通过 `db.query(...)` 链式构建查询；async 版本使用 SQLAlchemy 2.0
    `select(...)` 语法，并通过 `await db.execute(...)` 执行。筛选条件复用
    `_apply_test_point_filters_async` helper，与 sync `_build_test_point_filters`
    保持等价语义。
"""
from datetime import date, datetime, time
from typing import List, Optional, Tuple

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_point import TestPoint

# 复用 sync 模块中的排序字段映射，保证 sort_by 语义一致
from app.crud.test_point_management import SORT_FIELD_MAP


def _apply_test_point_filters_async(
    stmt,
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
    """构建测试点管理页的通用筛选条件（async select 版本）。

    语义与 sync `_build_test_point_filters` 完全一致：JOIN Project 校验 user_id
    归属，并按需追加 module / priority / created_by / requirement_id / keyword
    / created_from / created_to 等过滤条件。
    """
    stmt = stmt.join(Project, Project.id == TestPoint.project_id).where(
        TestPoint.project_id == project_id,
        Project.user_id == user_id,
    )
    if module:
        stmt = stmt.where(TestPoint.module == module)
    if apply_priority and priority is not None:
        stmt = stmt.where(TestPoint.priority == priority)
    if created_by:
        stmt = stmt.where(TestPoint.created_by == created_by)
    if requirement_id is not None:
        stmt = stmt.where(TestPoint.requirement_id == requirement_id)
    if keyword:
        keyword_like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                TestPoint.module.ilike(keyword_like),
                TestPoint.point.ilike(keyword_like),
            )
        )
    if created_from:
        stmt = stmt.where(
            TestPoint.create_time >= datetime.combine(created_from, time.min)
        )
    if created_to:
        stmt = stmt.where(
            TestPoint.create_time <= datetime.combine(created_to, time.max)
        )
    return stmt


async def get_test_points_with_case_count_async(
    db: AsyncSession,
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
    """获取带关联用例数量的测试点列表（async 版本）。

    语义与 sync `get_test_points_with_case_count` 一致：通过子查询聚合每个
    测试点关联的用例数量，外连接到 TestPoint，再叠加筛选 / 排序 / 分页。
    """
    case_count_subquery = (
        select(
            TestCase.test_point_id.label("test_point_id"),
            func.count(TestCase.id).label("test_case_count"),
        )
        .where(
            TestCase.project_id == project_id,
            TestCase.test_point_id.isnot(None),
            TestCase.is_deleted.is_(False),
        )
        .group_by(TestCase.test_point_id)
        .subquery()
    )

    stmt = select(
        TestPoint,
        func.coalesce(case_count_subquery.c.test_case_count, 0).label("test_case_count"),
    ).outerjoin(
        case_count_subquery,
        case_count_subquery.c.test_point_id == TestPoint.id,
    )

    stmt = _apply_test_point_filters_async(
        stmt=stmt,
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
    stmt = stmt.order_by(order_by_clause, desc(TestPoint.id)).offset(skip).limit(limit)

    result = await db.execute(stmt)
    return list(result.all())


async def get_test_points_with_case_count_total_async(
    db: AsyncSession,
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
    """获取增强筛选后的测试点总数（async 版本）。"""
    stmt = _apply_test_point_filters_async(
        stmt=select(func.count(TestPoint.id)),
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
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def get_test_point_list_stats_async(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
    keyword: Optional[str] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
) -> dict:
    """获取测试点列表的全局统计信息（async 版本）。

    统计会忽略当前优先级筛选，以便前端卡片可以作为优先级切换入口。
    """
    case_count_subquery = (
        select(
            TestCase.test_point_id.label("test_point_id"),
            func.count(TestCase.id).label("test_case_count"),
        )
        .where(
            TestCase.project_id == project_id,
            TestCase.test_point_id.isnot(None),
            TestCase.is_deleted.is_(False),
        )
        .group_by(TestCase.test_point_id)
        .subquery()
    )

    stmt = select(
        TestPoint.priority,
        func.coalesce(case_count_subquery.c.test_case_count, 0).label("test_case_count"),
    ).outerjoin(
        case_count_subquery,
        case_count_subquery.c.test_point_id == TestPoint.id,
    )

    stmt = _apply_test_point_filters_async(
        stmt=stmt,
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

    result = await db.execute(stmt)
    rows = result.all()

    stats = {
        "total": 0,
        "high_priority_count": 0,
        "medium_priority_count": 0,
        "low_priority_count": 0,
        "generated_case_count": 0,
    }
    for priority_value, test_case_count in rows:
        stats["total"] += 1
        stats["generated_case_count"] += int(test_case_count or 0)
        if priority_value == 1:
            stats["high_priority_count"] += 1
        elif priority_value == 2:
            stats["medium_priority_count"] += 1
        elif priority_value == 3:
            stats["low_priority_count"] += 1
    return stats
