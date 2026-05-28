"""Self-test project helpers."""
import json
import os
from typing import Any

from sqlalchemy.orm import Session

from app.models.project import Project


SELF_TEST_PROJECT_NAME = "AI TestMaster 自测项目"


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


def get_self_test_project(db: Session) -> Project | None:
    return (
        db.query(Project)
        .filter(Project.is_self_test.is_(True))
        .order_by(Project.id.asc())
        .first()
    )


def create_self_test_project(db: Session, user_id: int) -> Project:
    existing = get_self_test_project(db)
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
    db.commit()
    db.refresh(project)
    return project


__all__ = [
    "SELF_TEST_PROJECT_NAME",
    "_get_self_test_env_configs",
    "get_self_test_project",
    "create_self_test_project",
]
