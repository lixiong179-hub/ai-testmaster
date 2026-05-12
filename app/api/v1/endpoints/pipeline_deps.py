"""Pipeline 权限校验工具

提供项目与迭代级别的权限校验函数，供各子模块共用。
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.iteration import Iteration


def verify_project_access(db: Session, project_id: int, current_user: User) -> None:
    """校验当前用户是否拥有指定项目的操作权限。"""
    from app.models.project import Project
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此项目")


def verify_iteration_access(
    db: Session, iteration_id: int, current_user: User
) -> Iteration:
    """校验当前用户是否拥有指定迭代的操作权限，返回迭代对象。"""
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if not iteration:
        raise HTTPException(status_code=404, detail="迭代不存在")
    from app.models.project import Project
    project = db.query(Project).filter(
        Project.id == iteration.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此迭代的 Pipeline")
    return iteration
