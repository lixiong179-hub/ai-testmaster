"""
自测项目服务单元测试

覆盖场景：
    - 创建自测项目（正常流程）
    - 幂等性（重复创建返回已有项目）
    - 自测项目不可删除
    - 环境变量配置读取
"""
import json
import os
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.services.self_test_service import (
    create_self_test_project,
    get_self_test_project,
    _get_self_test_env_configs,
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
