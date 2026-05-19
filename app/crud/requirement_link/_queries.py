from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.requirement_link import RequirementLink
from app.models.project import Project
from app.utils.db_time import utcnow


def create_requirement_link(
    db: Session,
    project_id: int,
    link_name: str,
    link_type: str,
    link_url: str,
    created_by: Optional[int] = None,
    auth_type: str = "none",
    auth_config: Optional[Dict[str, Any]] = None,
    description: Optional[str] = None,
    cache_expire_minutes: int = 60
) -> RequirementLink:
    db_link = RequirementLink(
        project_id=project_id,
        link_name=link_name,
        link_type=link_type,
        link_url=link_url,
        created_by=created_by,
        auth_type=auth_type,
        auth_config=auth_config,
        description=description,
        cache_expire_minutes=cache_expire_minutes
    )
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link


def get_requirement_link_by_id(
    db: Session,
    link_id: int,
    project_id: Optional[int] = None
) -> Optional[RequirementLink]:
    query = db.query(RequirementLink).filter(RequirementLink.id == link_id)
    if project_id:
        query = query.filter(RequirementLink.project_id == project_id)
    return query.first()


def get_requirement_links_by_project(
    db: Session,
    project_id: int,
    user_id: int,
    link_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
) -> List[RequirementLink]:
    query = db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id
    )
    if link_type:
        query = query.filter(RequirementLink.link_type == link_type)
    if is_active is not None:
        query = query.filter(RequirementLink.is_active == is_active)
    return query.order_by(RequirementLink.create_time.desc()).offset(skip).limit(limit).all()


def get_requirement_links_count(
    db: Session,
    project_id: int,
    user_id: int,
    link_type: Optional[str] = None,
    is_active: Optional[bool] = None
) -> int:
    query = db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id
    )
    if link_type:
        query = query.filter(RequirementLink.link_type == link_type)
    if is_active is not None:
        query = query.filter(RequirementLink.is_active == is_active)
    return query.count()


def get_requirement_links_by_types(
    db: Session,
    project_id: int,
    user_id: int,
    link_types: List[str]
) -> List[RequirementLink]:
    return db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id,
        RequirementLink.link_type.in_(link_types),
        RequirementLink.is_active == True
    ).all()
