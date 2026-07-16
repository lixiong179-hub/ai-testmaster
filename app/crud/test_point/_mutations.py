from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.test_point import TestPoint
from app.models.enums import TestPointStatus
from app.crud.test_point._queries import get_test_point_by_id


def update_test_point(
    db: Session,
    test_point_id: int,
    project_id: int,
    **kwargs
) -> Optional[TestPoint]:
    test_point = get_test_point_by_id(db, test_point_id, project_id)
    if not test_point:
        return None
    for key, value in kwargs.items():
        if hasattr(test_point, key):
            setattr(test_point, key, value)
    test_point.version = (test_point.version or 1) + 1
    db.commit()
    db.refresh(test_point)
    return test_point


def delete_test_point(
    db: Session,
    test_point_id: int,
    project_id: int
) -> bool:
    test_point = get_test_point_by_id(db, test_point_id, project_id)
    if not test_point:
        return False
    db.delete(test_point)
    db.commit()
    return True


def batch_create_test_points(
    db: Session,
    project_id: int,
    test_points_data: List[Dict[str, Any]],
    created_by: Optional[str] = None,
    commit: bool = True,
) -> List[TestPoint]:
    test_points = []
    for data in test_points_data:
        test_point = TestPoint(
            project_id=project_id,
            module=data['module'],
            point=data['point'],
            priority=data['priority'],
            ai_prompt=data.get('ai_prompt'),
            created_by=data.get('created_by', created_by),
            requirement_id=data.get('requirement_id'),
            capability_id=data.get('capability_id'),
            status=data.get('status', TestPointStatus.ACTIVE.value),
        )
        db.add(test_point)
        test_points.append(test_point)

    db.flush()

    if commit:
        db.commit()
        for test_point in test_points:
            db.refresh(test_point)

    return test_points


async def batch_create_test_points_async(
    db: AsyncSession,
    project_id: int,
    test_points_data: List[Dict[str, Any]],
    created_by: Optional[str] = None,
    commit: bool = True,
) -> List[TestPoint]:
    """
    批量创建测试点（异步版本）

    batch_create_test_points 的异步实现，循环创建 TestPoint 对象并加入会话，
    flush 后根据 commit 参数决定是否提交事务并刷新对象。

    Args:
        db: 异步数据库会话
        project_id: 项目ID
        test_points_data: 测试点数据列表，每项为包含 module/point/priority 等字段的字典
        created_by: 创建人（可选），作为 data 中未指定 created_by 时的默认值
        commit: 是否提交事务，默认True

    Returns:
        List[TestPoint]: 创建的测试点对象列表
    """
    test_points = []
    for data in test_points_data:
        test_point = TestPoint(
            project_id=project_id,
            module=data['module'],
            point=data['point'],
            priority=data['priority'],
            ai_prompt=data.get('ai_prompt'),
            created_by=data.get('created_by', created_by),
            requirement_id=data.get('requirement_id'),
            capability_id=data.get('capability_id'),
            status=data.get('status', TestPointStatus.ACTIVE.value),
        )
        db.add(test_point)
        test_points.append(test_point)

    await db.flush()

    if commit:
        await db.commit()
        for test_point in test_points:
            await db.refresh(test_point)

    return test_points
