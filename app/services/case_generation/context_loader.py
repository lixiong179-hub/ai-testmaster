"""上下文构建 - 需求文档与UI原型数据加载
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.models.project import ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import file as file_crud
from app.services.file_content_extractor import get_file_content


async def load_requirement_content(
    db: Session,
    project_id: int,
    requirement_file_ids: Optional[List[int]],
    force_refresh: bool = False
) -> tuple[str, List[int]]:
    """加载需求文档内容。

    加载策略:
        1. 指定requirement_file_ids -> 加载指定文件
        2. 未指定 -> 加载项目全部需求文件

    Args:
        db: 数据库会话。
        project_id: 项目ID。
        requirement_file_ids: 需求文件ID列表，可选。
        force_refresh: 是否强制刷新文件内容。

    Returns:
        (需求内容文本, 使用的文件ID列表)
    """
    content_parts = []
    files_used = []

    if requirement_file_ids:
        for file_id in requirement_file_ids:
            file_record = file_crud.get_file_by_id(db, file_id, project_id)
            if file_record and file_record.resource_type == "requirement":
                content = file_record.content or ""
                if force_refresh or not content:
                    content = await get_file_content(file_id)
                if content:
                    content_parts.append(f"\n\n【{file_record.file_name}】\n{content}")
                    files_used.append(file_id)

    if not content_parts:
        all_req_files = file_crud.get_project_files_by_type(db, project_id, "requirement")
        for file_record in all_req_files:
            content = file_record.content or ""
            if force_refresh or not content:
                content = await get_file_content(file_record.id)
            if content:
                content_parts.append(f"\n\n【{file_record.file_name}】\n{content}")
                files_used.append(file_record.id)

    return "\n".join(content_parts), files_used


async def load_ui_data(
    db: Session,
    project_id: int,
    ui_screen_ids: Optional[List[int]] = None,
    ui_file_ids: Optional[List[int]] = None
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[int]]:
    """加载UI原型数据。

    加载策略（按优先级）:
        1. 指定ui_screen_ids -> 加载指定屏幕（含UI规格）
        2. 指定ui_file_ids -> 加载指定文件及关联屏幕
        3. 均未指定 -> 加载项目全部已解析UI屏幕

    Args:
        db: 数据库会话。
        project_id: 项目ID。
        ui_screen_ids: UI屏幕ID列表，可选。
        ui_file_ids: UI文件ID列表，可选。

    Returns:
        (UI描述列表, UI规格列表, 使用的文件ID列表)
    """
    ui_descriptions = []
    ui_specs = []
    files_used = []

    if ui_screen_ids:
        screens = db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.id.in_(ui_screen_ids),
            UIPrototypeScreen.project_id == project_id
        ).all()
        screen_map = {s.id: s for s in screens}
        for screen_id in ui_screen_ids:
            screen = screen_map.get(screen_id)
            if screen:
                ui_desc = {
                    "screen_id": screen.id, "screen_name": screen.screen_name,
                    "prototype_name": screen.prototype_name, "parse_status": screen.parse_status,
                    "summary": screen.summary or "", "element_count": screen.element_count or 0,
                    "button_count": screen.button_count or 0, "input_count": screen.input_count or 0,
                    "description": screen.summary or ""
                }
                ui_descriptions.append(ui_desc)
                if screen.ui_spec:
                    ui_specs.append({
                        "screen_id": screen.id, "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec
                    })
    elif ui_file_ids:
        for file_id in ui_file_ids:
            file_record = file_crud.get_file_by_id(db, file_id, project_id)
            if file_record and file_record.resource_type == "ui_mockup":
                ui_desc = {
                    "file_name": file_record.file_name, "file_url": file_record.file_url,
                    "description": file_record.description or ""
                }
                ui_descriptions.append(ui_desc)
                files_used.append(file_id)
                linked_screens = db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.project_id == project_id,
                    UIPrototypeScreen.prototype_name == file_record.file_name,
                    UIPrototypeScreen.parse_status == "completed",
                    UIPrototypeScreen.ui_spec.isnot(None)
                ).all()
                for screen in linked_screens:
                    ui_specs.append({
                        "screen_id": screen.id, "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec
                    })

    if not ui_descriptions and not ui_specs:
        screens_with_spec = db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.project_id == project_id,
            UIPrototypeScreen.parse_status == "completed",
            UIPrototypeScreen.ui_spec.isnot(None)
        ).order_by(UIPrototypeScreen.screen_order).all()
        if screens_with_spec:
            for screen in screens_with_spec:
                ui_desc = {
                    "screen_id": screen.id, "screen_name": screen.screen_name,
                    "prototype_name": screen.prototype_name, "parse_status": screen.parse_status,
                    "summary": screen.summary or "", "element_count": screen.element_count or 0,
                    "button_count": screen.button_count or 0, "input_count": screen.input_count or 0,
                    "description": screen.summary or ""
                }
                ui_descriptions.append(ui_desc)
                if screen.ui_spec:
                    ui_specs.append({
                        "screen_id": screen.id, "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec
                    })
        else:
            all_ui_files = file_crud.get_project_files_by_type(db, project_id, "ui_mockup")
            for file_record in all_ui_files:
                ui_desc = {
                    "file_name": file_record.file_name, "file_url": file_record.file_url,
                    "description": file_record.description or ""
                }
                ui_descriptions.append(ui_desc)
                files_used.append(file_record.id)

    return ui_descriptions, ui_specs, files_used
