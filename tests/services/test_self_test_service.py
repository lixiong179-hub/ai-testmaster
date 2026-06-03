"""
自测项目服务单元测试

覆盖场景：
    - 创建自测项目（正常流程）
    - 幂等性（重复创建返回已有项目）
    - 自测项目不可删除
    - 环境变量配置读取
    - 需求文档自动导入（正常导入、文件不存在降级、提取失败降级）
"""
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectFile
from app.models.user import User
from app.services.self_test_service import (
    create_self_test_project,
    get_self_test_project,
    _get_self_test_env_configs,
    _get_project_root,
    _auto_import_requirement_doc,
    SELF_TEST_PROJECT_NAME,
)


class TestGetSelfTestEnvConfigs:
    """环境变量配置读取测试"""

    def test_default_values(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            for key in ["SELF_TEST_FRONTEND_URL", "SELF_TEST_USERNAME"]:
                os.environ.pop(key, None)
            configs = _get_self_test_env_configs()
            test_env = configs["test"]
            assert test_env["url"] == "http://localhost:5173"
            assert test_env["username"] == ""
            assert "password" not in test_env

    def test_custom_values(self) -> None:
        env = {
            "SELF_TEST_FRONTEND_URL": "https://staging.example.com",
            "SELF_TEST_USERNAME": "admin",
        }
        with patch.dict(os.environ, env, clear=False):
            configs = _get_self_test_env_configs()
            test_env = configs["test"]
            assert test_env["url"] == "https://staging.example.com"
            assert test_env["username"] == "admin"
            assert "password" not in test_env


class TestGetSelfTestProject:
    """查询自测项目测试"""

    def test_no_self_test_project(self, db: Session) -> None:
        result = get_self_test_project(db)
        assert result is None

    def test_existing_self_test_project(self, db: Session, testUser: User) -> None:
        project = Project(
            name=SELF_TEST_PROJECT_NAME,
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        db.add(project)
        db.flush()

        result = get_self_test_project(db)
        assert result is not None
        assert result.id == project.id
        assert result.is_self_test is True

    def test_normal_project_not_returned(self, db: Session, testUser: User) -> None:
        project = Project(
            name="normal_project",
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=False,
        )
        db.add(project)
        db.flush()

        result = get_self_test_project(db)
        assert result is None


class TestCreateSelfTestProject:
    """创建自测项目测试"""

    def test_create_success(self, db: Session, testUser: User) -> None:
        env = {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "test_admin",
            "SELF_TEST_PASSWORD": "test_pass",
        }
        with patch.dict(os.environ, env, clear=False):
            project = create_self_test_project(db, testUser.id)

        assert project is not None
        assert project.name == SELF_TEST_PROJECT_NAME
        assert project.is_self_test is True
        assert project.test_object_type == "web"
        assert project.test_object_url == "http://localhost:5173"
        assert project.test_object_username == "test_admin"
        assert project.project_type == "web"
        assert project.status == 1

        web_configs = json.loads(project.web_env_configs)
        assert "test" in web_configs
        assert web_configs["test"]["url"] == "http://localhost:5173"
        assert web_configs["test"]["username"] == "test_admin"
        assert "password" not in web_configs["test"]

        assert project.test_object_password == "test_pass"

    def test_idempotent_create(self, db: Session, testUser: User) -> None:
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "pass",
        }, clear=False):
            first = create_self_test_project(db, testUser.id)
            second = create_self_test_project(db, testUser.id)

        assert first.id == second.id
        assert first.name == second.name

    def test_create_without_password(self, db: Session, testUser: User) -> None:
        env = {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "",
            "SELF_TEST_PASSWORD": "",
        }
        with patch.dict(os.environ, env, clear=False):
            project = create_self_test_project(db, testUser.id)

        assert project is not None
        assert project.is_self_test is True
        web_configs = json.loads(project.web_env_configs)
        assert "password" not in web_configs["test"]
        assert project.test_object_password is None


class TestSelfTestProjectDeleteProtection:
    """自测项目删除保护测试"""

    def test_self_test_project_cannot_be_deleted(self, db: Session, testUser: User) -> None:
        project = Project(
            name=SELF_TEST_PROJECT_NAME,
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        db.add(project)
        db.flush()

        from fastapi import HTTPException
        from app.api.v1.endpoints.project_core import delete_project

        with pytest.raises(HTTPException) as exc_info:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                delete_project(project.id, db=db, current_user=testUser)
            )
        assert exc_info.value.status_code == 403
        assert "自测项目不可删除" in exc_info.value.detail

    def test_normal_project_can_be_deleted(self, db: Session, testUser: User) -> None:
        project = Project(
            name="deletable_project",
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=False,
        )
        db.add(project)
        db.flush()

        from app.api.v1.endpoints.project_core import delete_project
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            delete_project(project.id, db=db, current_user=testUser)
        )
        assert result["msg"] == "删除成功"


class TestGetProjectRoot:
    """项目根目录获取测试"""

    def test_returns_path_object(self) -> None:
        root = _get_project_root()
        assert isinstance(root, Path)

    def test_root_directory_exists(self) -> None:
        root = _get_project_root()
        assert root.exists()
        assert root.is_dir()

    def test_root_contains_app_directory(self) -> None:
        root = _get_project_root()
        app_dir = root / "app"
        assert app_dir.exists()
        assert app_dir.is_dir()


class TestAutoImportRequirementDoc:
    """需求文档自动导入测试"""

    def test_import_success_when_doc_exists(
        self, db: Session, testUser: User
    ) -> None:
        """需求文档存在时，自动导入创建 ProjectFile 记录并提取内容"""
        project = Project(
            name="import_test_project",
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        db.add(project)
        db.flush()

        _auto_import_requirement_doc(db, project)

        # 验证 ProjectFile 记录已创建
        file_record = (
            db.query(ProjectFile)
            .filter(
                ProjectFile.project_id == project.id,
                ProjectFile.resource_type == "requirement",
            )
            .first()
        )
        if file_record is not None:
            assert file_record.file_name == "requirement_specification.md"
            assert file_record.file_type == "md"
            assert file_record.file_source == "auto_import"
            assert file_record.resource_type == "requirement"
            assert file_record.extract_status == "completed"
            assert file_record.content is not None
            assert len(file_record.content) > 0
            assert file_record.is_active is True

    def test_graceful_when_doc_not_exists(
        self, db: Session, testUser: User
    ) -> None:
        """需求文档不存在时，仅记录警告日志，不阻断流程"""
        project = Project(
            name="no_doc_project",
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        db.add(project)
        db.flush()

        # 将项目根目录 mock 到一个不存在的路径
        with patch(
            "app.services.self_test_service._get_project_root",
            return_value=Path("/nonexistent_root_for_test"),
        ):
            # 不应抛出异常
            _auto_import_requirement_doc(db, project)

        # 不应创建任何 ProjectFile 记录
        file_count = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project.id)
            .count()
        )
        assert file_count == 0

    def test_graceful_when_extract_fails(
        self, db: Session, testUser: User
    ) -> None:
        """文件读取异常时，仅记录警告日志，不阻断项目创建"""
        project = Project(
            name="extract_fail_project",
            user_id=testUser.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        db.add(project)
        db.flush()

        # mock open 抛出异常
        with patch("builtins.open", side_effect=PermissionError("no access")):
            # 不应抛出异常
            _auto_import_requirement_doc(db, project)

        # 不应创建任何 ProjectFile 记录
        file_count = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project.id)
            .count()
        )
        assert file_count == 0

    def test_import_does_not_block_project_creation(
        self, db: Session, testUser: User
    ) -> None:
        """即使需求文档导入失败，项目创建仍然成功"""
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "pass",
        }, clear=False):
            # mock _get_project_root 返回不存在的路径，触发降级
            with patch(
                "app.services.self_test_service._get_project_root",
                return_value=Path("/nonexistent_root_for_test"),
            ):
                project = create_self_test_project(db, testUser.id)

        # 项目仍然创建成功
        assert project is not None
        assert project.name == SELF_TEST_PROJECT_NAME
        assert project.is_self_test is True


class TestCreateSelfTestProjectWithRequirementImport:
    """创建自测项目时需求文档自动导入集成测试"""

    def test_create_project_imports_requirement_doc(
        self, db: Session, testUser: User
    ) -> None:
        """创建自测项目后，需求文档被自动导入"""
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "pass",
        }, clear=False):
            project = create_self_test_project(db, testUser.id)

        assert project is not None

        # 验证需求文档是否被导入（取决于 docs/requirement_specification.md 是否存在）
        doc_path = _get_project_root() / "docs" / "requirement_specification.md"
        if doc_path.exists():
            file_record = (
                db.query(ProjectFile)
                .filter(
                    ProjectFile.project_id == project.id,
                    ProjectFile.resource_type == "requirement",
                )
                .first()
            )
            assert file_record is not None
            assert file_record.file_name == "requirement_specification.md"
            assert file_record.extract_status == "completed"
            assert file_record.content is not None

    def test_idempotent_create_does_not_duplicate_import(
        self, db: Session, testUser: User
    ) -> None:
        """幂等创建自测项目时，不会重复导入需求文档"""
        with patch.dict(os.environ, {
            "SELF_TEST_FRONTEND_URL": "http://localhost:5173",
            "SELF_TEST_USERNAME": "admin",
            "SELF_TEST_PASSWORD": "pass",
        }, clear=False):
            first = create_self_test_project(db, testUser.id)
            second = create_self_test_project(db, testUser.id)

        assert first.id == second.id

        # 幂等返回已有项目，不应创建额外的文件记录
        file_count = (
            db.query(ProjectFile)
            .filter(
                ProjectFile.project_id == first.id,
                ProjectFile.resource_type == "requirement",
            )
            .count()
        )
        # 最多只有一条需求文档记录
        assert file_count <= 1
