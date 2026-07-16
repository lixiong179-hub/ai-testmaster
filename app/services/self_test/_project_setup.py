"""Self-test project setup helpers."""
import json
import os
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectFile


SELF_TEST_PROJECT_NAME = "AI TestMaster 自测项目"

# 需求文档相对于项目根目录的路径
_REQUIREMENT_DOC_RELATIVE_PATH = Path("docs") / "requirement_specification.md"


def _get_project_root() -> Path:
    """获取项目根目录（self_test 子包的向上四级）。

    Returns:
        Path: 项目根目录的绝对路径。
    """
    return Path(__file__).resolve().parent.parent.parent.parent


async def _auto_import_requirement_doc(db: AsyncSession, project: Project) -> None:
    """自测项目创建后自动导入需求文档。

    读取 docs/requirement_specification.md，创建 ProjectFile 记录
    并触发文件内容提取。文件不存在或提取失败时仅记录警告日志，
    不阻断项目创建流程。

    通过 shim 模块引用调用 _get_project_root，使
    @patch("app.services.self_test_service._get_project_root") 仍能生效。

    Args:
        db: 异步数据库会话。
        project: 已创建的自测项目实例。
    """
    from app.services import self_test_service as _stm
    doc_path = _stm._get_project_root() / _REQUIREMENT_DOC_RELATIVE_PATH

    if not doc_path.exists():
        logger.warning(
            f"自测项目需求文档不存在，跳过自动导入: {doc_path}"
        )
        return

    try:
        file_size = doc_path.stat().st_size
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        project_file = ProjectFile(
            project_id=project.id,
            file_name=doc_path.name,
            file_type="md",
            file_url=str(doc_path),
            file_source="auto_import",
            size=file_size,
            resource_type="requirement",
            description="自测项目自动导入的需求规格说明书",
            extract_status="pending",
            is_active=True,
        )
        db.add(project_file)
        await db.commit()
        await db.refresh(project_file)

        # 直接写入提取内容（md 文件已读取到内存），避免异步调用
        from app.crud import file as file_crud
        await file_crud.update_file_content_async(db, project_file.id, content, "completed")

        logger.info(
            f"自测项目需求文档自动导入成功: project_id={project.id}, "
            f"file_id={project_file.id}"
        )
    except Exception as exc:
        logger.warning(
            f"自测项目需求文档自动导入失败，不影响项目创建: {exc}"
        )


def _get_self_test_env_configs() -> dict[str, dict[str, Any]]:
    """Build web environment config for the platform self-test project.

    Passwords are intentionally excluded from web_env_configs and are stored via
    Project.test_object_password so they go through the existing encryption path.
    """
    return {
        "test": {
            "url": os.getenv("SELF_TEST_FRONTEND_URL", "http://localhost:5173"),
            "username": os.getenv("SELF_TEST_USERNAME", ""),
        }
    }


async def get_self_test_project(db: AsyncSession) -> Project | None:
    return (
        await db.execute(
            select(Project)
            .where(Project.is_self_test.is_(True))
            .order_by(Project.id.asc())
        )
    ).scalars().first()


async def create_self_test_project(db: AsyncSession, user_id: int) -> Project:
    existing = await get_self_test_project(db)
    if existing:
        return existing

    configs = _get_self_test_env_configs()
    test_config = configs["test"]

    project = Project(
        name=SELF_TEST_PROJECT_NAME,
        user_id=user_id,
        status=1,
        project_type="web",
        is_self_test=True,
        test_object_type="web",
        test_object_url=test_config.get("url"),
        test_object_username=test_config.get("username"),
        web_env_configs=json.dumps(configs, ensure_ascii=False),
    )
    project.test_object_password = os.getenv("SELF_TEST_PASSWORD", "")

    db.add(project)
    await db.commit()
    await db.refresh(project)

    # 自动导入需求文档（降级处理：失败不阻断项目创建）
    await _auto_import_requirement_doc(db, project)

    return project
