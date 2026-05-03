"""幂等测试数据导入脚本

从 tests/data/project_xxx/ JSON 标注集初始化测试数据库中的基准项目数据。
支持 idempotent 模式：每次运行先删除该项目已有数据再插入。

用法：
    python scripts/prepare_test_data.py [--project alpha|beta|gamma|all]

环境变量：
    TEST_DATABASE_URL 测试数据库连接（可选，默认从 settings 推断）
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.utils.jwt_utils import get_password_hash

_DATA_DIR = Path(__file__).resolve().parent.parent / "tests" / "data"

_DEFAULT_TEST_DB = os.getenv(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.replace("/ai_testmaster", "/ai_testmaster_test")
    if "/ai_testmaster" in settings.DATABASE_URL
    else settings.DATABASE_URL,
)


def _build_engine() -> Engine:
    return create_engine(
        _DEFAULT_TEST_DB,
        pool_size=1,
        pool_pre_ping=True,
        connect_args={"init_command": "SET sql_mode='NO_ENGINE_SUBSTITUTION'"},
    )


def _load_json(project_dir_name: str, filename: str) -> dict:
    filepath = _DATA_DIR / project_dir_name / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _clear_project(session: Session, project_id: int):
    from app.models.test_case import TestCase
    from app.models.test_point import TestPoint
    from app.models.iteration import Iteration, IterationInput
    from app.models.ui_prototype import UIPrototypeScreen

    session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    try:
        session.query(IterationInput).filter(
            IterationInput.iteration_id.in_(
                session.query(Iteration.id).filter(Iteration.project_id == project_id)
            )
        ).delete(synchronize_session=False)
        session.query(Iteration).filter(Iteration.project_id == project_id).delete(synchronize_session=False)
        session.query(TestCase).filter(TestCase.project_id == project_id).delete(synchronize_session=False)
        session.query(TestPoint).filter(TestPoint.project_id == project_id).delete(synchronize_session=False)
        session.query(UIPrototypeScreen).filter(UIPrototypeScreen.project_id == project_id).delete(
            synchronize_session=False
        )
        session.flush()
    finally:
        session.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def _import_alpha(session: Session, user_id: int):
    project_data = _load_json("project_alpha", "project.json")
    test_points = _load_json("project_alpha", "test_points.json")
    ui_data = _load_json("project_alpha", "ui_prototype.json")
    expected_cases = _load_json("project_alpha", "expected_cases.json")

    from app.models.project import Project

    project = Project(
        name=project_data["name"],
        project_type=project_data.get("project_type", "web"),
        description=project_data.get("description", ""),
        status=1,
        user_id=user_id,
    )
    session.add(project)
    session.flush()

    from app.models.test_point import TestPoint

    for tp in test_points:
        db_tp = TestPoint(
            project_id=project.id,
            module=tp["module"],
            point=tp["point"],
            priority=tp["priority"],
        )
        session.add(db_tp)
        session.flush()

    from app.models.ui_prototype import UIPrototypeScreen

    for idx, screen in enumerate(ui_data):
        ui_screen = UIPrototypeScreen(
            project_id=project.id,
            prototype_name="alpha_proto",
            screen_name=screen["screen_name"],
            source="manual",
            screen_order=idx,
            parse_status="completed",
            summary=screen.get("description", ""),
            ui_spec={"components": screen.get("components", [])},
        )
        session.add(ui_screen)

    from app.models.test_case import TestCase

    for idx, case in enumerate(expected_cases):
        db_case = TestCase(
            project_id=project.id,
            case_no=f"{project.id}-ALPHA-{idx + 1:03d}",
            module=case["module"],
            title=case["title"],
            precondition=case["precondition"],
            steps_json=case["steps"],
            expected_result=case["expected_result"],
            priority=case["priority"],
            case_type=case.get("case_type", "functional"),
        )
        session.add(db_case)

    session.commit()
    print(f"[Alpha] 项目 id={project.id}，测试点 {len(test_points)} 条，"
          f"UI屏幕 {len(ui_data)} 个，预期用例 {len(expected_cases)} 条")


def _import_beta(session: Session, user_id: int):
    project_data = _load_json("project_beta", "project.json")
    historical_cases = _load_json("project_beta", "historical_cases.json")

    from app.models.project import Project

    project = Project(
        name=project_data["name"],
        project_type=project_data.get("project_type", "web"),
        description=project_data.get("description", ""),
        status=1,
        user_id=user_id,
    )
    session.add(project)
    session.flush()

    from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition

    enable_lifecycle_transition()
    try:
        for case in historical_cases:
            db_case = TestCase(
                project_id=project.id,
                case_no=case["case_no"],
                module=case["module"],
                title=case["title"],
                precondition=case["precondition"],
                steps_json=case["steps_json"],
                expected_result=case["expected_result"],
                priority=case["priority"],
                case_type=case.get("case_type", "functional"),
                lifecycle_status="active",
                summary=case.get("summary", ""),
            )
            session.add(db_case)
        session.flush()
    finally:
        disable_lifecycle_transition()

    session.commit()
    print(f"[Beta] 项目 id={project.id}，历史用例 {len(historical_cases)} 条"
          f"（含 4 模块：用户注册/登录/密码找回/个人信息管理）")


def _import_gamma(session: Session, user_id: int):
    project_data = _load_json("project_gamma", "project.json")
    ui_data = _load_json("project_gamma", "ui_prototype.json")

    from app.models.project import Project

    project = Project(
        name=project_data["name"],
        project_type=project_data.get("project_type", "web"),
        description=project_data.get("description", ""),
        status=1,
        user_id=user_id,
    )
    session.add(project)
    session.flush()

    from app.models.ui_prototype import UIPrototypeScreen

    for idx, screen in enumerate(ui_data):
        ui_screen = UIPrototypeScreen(
            project_id=project.id,
            prototype_name="gamma_proto",
            screen_name=screen["screen_name"],
            source="manual",
            screen_order=idx,
            parse_status="completed",
            summary=screen.get("description", ""),
            ui_spec={"components": screen.get("components", [])},
        )
        session.add(ui_screen)

    session.commit()
    print(f"[Gamma] 项目 id={project.id}，UI 屏幕 {len(ui_data)} 个（仅 UI，无 PRD/测试点/用例）")


_PROJECTS = {"alpha": _import_alpha, "beta": _import_beta, "gamma": _import_gamma}


def _get_or_create_user(session: Session) -> int:
    from app.models.user import User

    user = session.query(User).filter(User.username == "prepare_test_user").first()
    if user:
        return user.id

    user = User(
        username="prepare_test_user",
        email="prepare_test@test.com",
        password_hash=get_password_hash("Prepare@123456"),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)
    session.flush()
    return user.id


def main():
    parser = argparse.ArgumentParser(description="幂等测试数据导入脚本")
    parser.add_argument(
        "--project",
        choices=["alpha", "beta", "gamma", "all"],
        default="all",
        help="要初始化的标注项目（默认 all）",
    )
    args = parser.parse_args()

    engine = _build_engine()
    SessionLocal = sessionmaker(bind=engine)

    targets = list(_PROJECTS.keys()) if args.project == "all" else [args.project]

    session: Optional[Session] = None
    try:
        session = SessionLocal()
        user_id = _get_or_create_user(session)

        from app.models.project import Project as PM

        for target in targets:
            existing = session.query(PM).filter(PM.name.like(f"%{target.capitalize()}%")).first()
            if existing:
                print(f"[{target.capitalize()}] 删除已有项目 id={existing.id} ...")
                _clear_project(session, existing.id)
                session.query(PM).filter(PM.id == existing.id).delete()
                session.commit()

            _PROJECTS[target](session, user_id)

        print("全部完成。")
    except Exception:
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
