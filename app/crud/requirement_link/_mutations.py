from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.requirement_link import RequirementLink
from app.models.project import Project
from app.utils.db_time import utcnow
from app.crud.requirement_link._queries import get_requirement_link_by_id


def update_requirement_link(
    db: Session,
    link_id: int,
    project_id: Optional[int] = None,
    **kwargs
) -> Optional[RequirementLink]:
    link = get_requirement_link_by_id(db, link_id, project_id)
    if not link:
        return None
    protected_fields = ['id', 'project_id', 'created_by', 'create_time']
    for key, value in kwargs.items():
        if key not in protected_fields and hasattr(link, key):
            setattr(link, key, value)
    link.update_time = utcnow()
    db.commit()
    db.refresh(link)
    return link


def delete_requirement_link(
    db: Session,
    link_id: int,
    project_id: Optional[int] = None
) -> bool:
    link = get_requirement_link_by_id(db, link_id, project_id)
    if not link:
        return False
    db.delete(link)
    db.commit()
    return True


def update_link_cache(
    db: Session,
    link_id: int,
    cached_content: str,
    fetch_status: str = "success"
) -> Optional[RequirementLink]:
    link = db.query(RequirementLink).filter(RequirementLink.id == link_id).first()
    if not link:
        return None
    link.cached_content = cached_content
    link.last_fetch_time = utcnow()
    link.last_fetch_status = fetch_status
    link.update_time = utcnow()
    db.commit()
    db.refresh(link)
    return link


def get_active_links_by_project(
    db: Session,
    project_id: int,
    user_id: int
) -> List[RequirementLink]:
    return db.query(RequirementLink).join(Project).filter(
        RequirementLink.project_id == project_id,
        Project.user_id == user_id,
        RequirementLink.is_active == True
    ).order_by(RequirementLink.link_type, RequirementLink.create_time.desc()).all()


def toggle_link_active(
    db: Session,
    link_id: int,
    project_id: int,
    user_id: int
) -> Optional[RequirementLink]:
    link = db.query(RequirementLink).join(Project).filter(
        RequirementLink.id == link_id,
        RequirementLink.project_id == project_id,
        Project.user_id == user_id
    ).first()
    if not link:
        return None
    link.is_active = not link.is_active
    link.update_time = utcnow()
    db.commit()
    db.refresh(link)
    return link


def check_link_exists(
    db: Session,
    project_id: int,
    link_url: str
) -> bool:
    return db.query(RequirementLink).filter(
        RequirementLink.project_id == project_id,
        RequirementLink.link_url == link_url
    ).first() is not None
