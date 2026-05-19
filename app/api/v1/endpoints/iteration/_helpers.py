import os
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen, UIScreenTestCaseLink
from app.models.user import User
from loguru import logger


def _verify_project_ownership(db: Session, project_id: int, current_user: User) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


def _iteration_to_dict(iteration):
    result = {
        "id": iteration.id,
        "project_id": iteration.project_id,
        "name": iteration.name,
        "version": iteration.version,
        "description": iteration.description,
        "status": iteration.status,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "base_iteration_id": iteration.base_iteration_id,
        "created_by": iteration.created_by,
        "finalized_at": iteration.finalized_at,
        "create_time": iteration.create_time,
        "update_time": iteration.update_time,
    }
    inputs = getattr(iteration, 'inputs', None)
    if inputs is not None:
        result["inputs"] = [
            {
                "id": inp.id,
                "iteration_id": inp.iteration_id,
                "kind": inp.kind,
                "file_id": inp.file_id,
                "payload": inp.payload,
                "content_hash": inp.content_hash,
                "uploaded_at": inp.uploaded_at,
            }
            for inp in inputs
        ]
    return result


def _cleanup_iteration_resources(db: Session, iteration_id: int):
    project_files = db.query(ProjectFile).filter(
        ProjectFile.iteration_id == iteration_id
    ).all()
    for pf in project_files:
        pf.is_active = False

    ui_prototype_projects = db.query(UIPrototypeProject).filter(
        UIPrototypeProject.iteration_id == iteration_id
    ).all()
    for proto_project in ui_prototype_projects:
        screens = db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.prototype_project_id == proto_project.id
        ).all()
        for screen in screens:
            if screen.original_file_path and os.path.exists(screen.original_file_path):
                try:
                    os.remove(screen.original_file_path)
                except OSError as e:
                    logger.warning(f"删除UI原型文件失败: {screen.original_file_path}, 错误: {e}")
            db.query(UIScreenTestCaseLink).filter(
                UIScreenTestCaseLink.screen_id == screen.id
            ).delete()
            db.delete(screen)
        db.delete(proto_project)
