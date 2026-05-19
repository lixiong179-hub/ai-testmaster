from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.ui_prototype import UIPrototypeScreen, UIScreenTestCaseLink
from app.utils.db_time import utcnow


def create_ui_screen(
    db: Session,
    project_id: int,
    prototype_name: str,
    screen_name: str,
    original_file_path: Optional[str] = None,
    original_file_name: Optional[str] = None,
    file_type: str = "png",
    file_size: Optional[int] = None,
    screen_order: int = 0,
    created_by: Optional[int] = None,
    prototype_project_id: Optional[int] = None,
) -> UIPrototypeScreen:
    db_screen = UIPrototypeScreen(
        project_id=project_id,
        prototype_name=prototype_name,
        screen_name=screen_name,
        original_file_path=original_file_path,
        original_file_name=original_file_name,
        file_type=file_type,
        file_size=file_size,
        screen_order=screen_order,
        created_by=created_by,
        prototype_project_id=prototype_project_id,
        parse_status="pending",
    )
    db.add(db_screen)
    db.commit()
    db.refresh(db_screen)
    return db_screen


def batch_create_ui_screens(
    db: Session,
    project_id: int,
    screens_data: List[Dict[str, Any]],
    created_by: Optional[int] = None,
    prototype_project_id: Optional[int] = None,
) -> List[UIPrototypeScreen]:
    screens = []
    for data in screens_data:
        screen = UIPrototypeScreen(
            project_id=project_id,
            prototype_name=data.get("prototype_name", "未命名"),
            screen_name=data.get("screen_name", data.get("file_name", "屏幕")),
            original_file_path=data.get("file_path"),
            original_file_name=data.get("file_name"),
            file_type=data.get("file_type", "png"),
            file_size=data.get("file_size"),
            screen_order=data.get("screen_order", 0),
            created_by=created_by,
            prototype_project_id=prototype_project_id or data.get("prototype_project_id"),
            parse_status="pending",
        )
        db.add(screen)
        screens.append(screen)
    db.commit()
    for screen in screens:
        db.refresh(screen)
    return screens


def delete_ui_screen(db: Session, screen_id: int) -> bool:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return False
    db.query(UIScreenTestCaseLink).filter(
        UIScreenTestCaseLink.screen_id == screen_id
    ).delete()
    db.delete(screen)
    db.commit()
    return True
