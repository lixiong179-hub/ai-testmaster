"""UI 原型解析端点的后台任务与 sync 验证函数。

从 parse_endpoints.py 拆出，封装后台解析逻辑和 db.run_sync 桥接函数，
便于独立测试与复用。
"""
import traceback

from loguru import logger
from sqlalchemy.orm import Session

from app.crud import ui_prototype as ui_prototype_crud
from app.db.database import get_db_context
from app.models.project import Project
from app.models.ui_prototype import UIPrototypeProject
from app.services.ui_spec_parse_pipeline import UISpecParsePipeline
from app.api.v1.endpoints.ui_prototype.helpers import UPLOAD_DIR


async def run_parse_background(
    screen_ids: list[int],
    target_project_id: int,
    user_id: int,
    parse_mode: str,
    prototype_project_id: int | None,
) -> None:
    """后台执行单屏/多屏解析。

    使用独立数据库会话，避免请求会话被关闭。
    不预设 running 状态，由 pipeline.parse_screen() 逐屏设置，保证进度条渐进推进。
    """
    try:
        with get_db_context() as bg_db:
            pipeline = UISpecParsePipeline(
                bg_db, target_project_id, user_id, UPLOAD_DIR,
                parse_mode=parse_mode,
            )
            result = await pipeline.batch_parse_screens(screen_ids)

            if prototype_project_id:
                ui_prototype_crud.update_prototype_project_stats(
                    bg_db, prototype_project_id
                )

        logger.info(
            f"[后台解析完成] project_id={target_project_id} "
            f"success={result.get('success', 0)} failed={result.get('failed', 0)}"
        )
    except Exception as e:
        logger.error(f"[后台解析异常] {e}\n{traceback.format_exc()}")
        # 将仍在 running 或 pending 状态的屏幕标记为 failed
        try:
            with get_db_context() as bg_db:
                for screen_id in screen_ids:
                    screen = ui_prototype_crud.get_ui_screen_by_id(
                        bg_db, screen_id, target_project_id
                    )
                    if screen and screen.parse_status in ("running", "pending"):
                        ui_prototype_crud.update_ui_screen_parse_status(
                            bg_db, screen_id, "failed", str(e)
                        )
        except Exception as mark_err:
            logger.error(f"[后台解析] 标记失败状态异常: {mark_err}")


async def run_project_parse_background(
    prototype_project_id: int,
    project_id: int,
    user_id: int,
    parse_mode: str,
) -> None:
    """后台执行原型项目解析（按项目维度）。

    使用独立数据库会话，由 pipeline 逐屏设置状态。
    """
    try:
        with get_db_context() as bg_db:
            pipeline = UISpecParsePipeline(
                bg_db, project_id, user_id, UPLOAD_DIR,
                parse_mode=parse_mode,
            )
            result = await pipeline.parse_prototype_project(prototype_project_id)

        logger.info(
            f"[后台项目解析完成] prototype_project_id={prototype_project_id} "
            f"success={result.get('success', 0)} failed={result.get('failed', 0)}"
        )
    except Exception as e:
        logger.error(f"[后台项目解析异常] {e}\n{traceback.format_exc()}")
        # 将仍在 running 或 pending 状态的屏幕标记为 failed
        try:
            with get_db_context() as bg_db:
                for status_to_mark in ("running", "pending"):
                    stuck_screens = ui_prototype_crud.get_ui_screens_by_project(
                        db=bg_db,
                        project_id=project_id,
                        user_id=user_id,
                        prototype_project_id=prototype_project_id,
                        parse_status=status_to_mark,
                    )
                    for s in stuck_screens:
                        ui_prototype_crud.update_ui_screen_parse_status(
                            bg_db, s.id, "failed", str(e)
                        )
        except Exception as mark_err:
            logger.error(f"[后台项目解析] 标记失败状态异常: {mark_err}")


def validate_and_create_pipeline_for_flow(
    sync_db: Session,
    prototype_project_id: int,
    user_id: int,
) -> UISpecParsePipeline:
    """sync 版本：校验原型项目归属并创建 UISpecParsePipeline。

    用于 generate_page_flow 端点的 db.run_sync 桥接。
    """
    prototype_project = (
        sync_db.query(UIPrototypeProject)
        .filter(UIPrototypeProject.id == prototype_project_id)
        .first()
    )
    if not prototype_project:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="原型项目不存在"
        )

    db_project = (
        sync_db.query(Project)
        .filter(
            Project.id == prototype_project.project_id,
            Project.user_id == user_id,
        )
        .first()
    )
    if not db_project:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目或项目不存在",
        )

    return UISpecParsePipeline(sync_db, db_project.id, user_id, UPLOAD_DIR)


def get_ui_specs_sync(
    sync_db: Session,
    project_id: int,
    user_id: int,
    prototype_project_id: int | None,
) -> list:
    """sync 版本：校验项目权限并获取 UI specs（供用例生成）。

    用于 get_ui_specs_for_case_generation 端点的 db.run_sync 桥接。
    """
    project = (
        sync_db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )

    pipeline = UISpecParsePipeline(sync_db, project_id, user_id, UPLOAD_DIR)
    return pipeline.get_parsed_ui_spec_for_case_generation(prototype_project_id)


__all__ = [
    "run_parse_background",
    "run_project_parse_background",
    "validate_and_create_pipeline_for_flow",
    "get_ui_specs_sync",
]
