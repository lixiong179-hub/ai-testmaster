from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.test_point import TestPoint
from app.models.project import Project
from app.models.enums import TestPointStatus


def create_test_point(
    db: Session,
    project_id: int,
    module: str,
    point: str,
    priority: int,
    ai_prompt: Optional[str] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
    capability_id: Optional[int] = None,
    status: Optional[str] = None,
) -> TestPoint:
    db_test_point = TestPoint(
        project_id=project_id,
        module=module,
        point=point,
        priority=priority,
        ai_prompt=ai_prompt,
        created_by=created_by,
        requirement_id=requirement_id,
        capability_id=capability_id,
        status=status or TestPointStatus.ACTIVE.value,
    )
    db.add(db_test_point)
    db.commit()
    db.refresh(db_test_point)
    return db_test_point


def get_test_point_by_id(
    db: Session,
    test_point_id: int,
    project_id: int
) -> Optional[TestPoint]:
    return db.query(TestPoint).filter(
        TestPoint.id == test_point_id,
        TestPoint.project_id == project_id
    ).first()


def get_test_points_by_project(
    db: Session,
    project_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestPoint]:
    query = db.query(TestPoint).filter(TestPoint.project_id == project_id)
    if module:
        query = query.filter(TestPoint.module == module)
    if priority:
        query = query.filter(TestPoint.priority == priority)
    return query.offset(skip).limit(limit).all()


def get_test_points_by_project_and_user(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestPoint]:
    query = db.query(TestPoint).join(Project).filter(
        TestPoint.project_id == project_id,
        Project.user_id == user_id
    )
    if module:
        query = query.filter(TestPoint.module == module)
    if priority:
        query = query.filter(TestPoint.priority == priority)
    return query.offset(skip).limit(limit).all()


def get_test_points_count(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None
) -> int:
    query = db.query(TestPoint).join(Project).filter(
        TestPoint.project_id == project_id,
        Project.user_id == user_id
    )
    if module:
        query = query.filter(TestPoint.module == module)
    if priority:
        query = query.filter(TestPoint.priority == priority)
    return query.count()
