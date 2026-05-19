from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.ui_prototype import UIPrototypeScreen, UIScreenTestCaseLink
from app.utils.db_time import utcnow


def update_ui_screen_parse_result(
    db: Session,
    screen_id: int,
    ui_spec: Dict[str, Any],
    parse_model: str,
    summary: Optional[str] = None,
    element_count: int = 0,
    button_count: int = 0,
    input_count: int = 0,
    layout_checks: Optional[List[Dict]] = None,
    navigation_flow: Optional[Dict] = None,
    is_entry_point: bool = False,
    is_end_point: bool = False,
) -> Optional[UIPrototypeScreen]:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.ui_spec = ui_spec
    screen.parse_status = "completed"
    screen.parse_model = parse_model
    screen.parse_error = None
    screen.summary = summary
    screen.element_count = element_count
    screen.button_count = button_count
    screen.input_count = input_count
    screen.layout_checks = layout_checks
    screen.navigation_flow = navigation_flow
    screen.is_entry_point = is_entry_point
    screen.is_end_point = is_end_point
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def update_ui_screen_parse_status(
    db: Session,
    screen_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[UIPrototypeScreen]:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.parse_status = status
    if error_message:
        screen.parse_error = error_message
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def update_ui_screen_review(
    db: Session,
    screen_id: int,
    review_status: str,
    reviewer: Optional[str] = None,
    review_comment: Optional[str] = None,
) -> Optional[UIPrototypeScreen]:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.review_status = review_status
    screen.reviewed_by = reviewer
    screen.reviewed_at = utcnow()
    screen.review_comment = review_comment
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def update_ui_screen_order(
    db: Session, screen_id: int, screen_order: int
) -> Optional[UIPrototypeScreen]:
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.screen_order = screen_order
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def link_ui_screen_to_test_case(
    db: Session, screen_id: int, test_case_id: int, link_type: str = "source"
) -> UIScreenTestCaseLink:
    existing = db.query(UIScreenTestCaseLink).filter(
        UIScreenTestCaseLink.screen_id == screen_id,
        UIScreenTestCaseLink.test_case_id == test_case_id,
    ).first()
    if existing:
        existing.link_type = link_type
        db.commit()
        return existing
    link = UIScreenTestCaseLink(
        screen_id=screen_id, test_case_id=test_case_id, link_type=link_type
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
