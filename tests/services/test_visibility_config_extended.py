import time
import pytest
from unittest.mock import patch, MagicMock
from app.services.visibility_config.permission_mixin import VisibilityConfigPermissionMixin
from app.services.visibility_config.core_mixin import VisibilityConfigCoreMixin
from app.services.visibility_config.models import VisibilityConfig
from app.services.visibility_config.validator import VisibilityConfigValidator
from app.services.visibility_config.merger import VisibilityConfigMerger
from app.services.visibility_config.env_loader import VisibilityEnvLoader
from app.models.project import Project
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.user import User


def _create_task(db, testUser, **kwargs):
    project = Project(
        name=f"vis_task_proj_{int(time.time()*1000)}",
        user_id=testUser.id,
        description="test",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    defaults = dict(
        task_name=f"vis_task_{int(time.time()*1000)}",
        project_id=project.id,
        executor_id=testUser.id,
        case_ids=[],
        status=0,
        total_count=0,
        success_count=0,
        fail_count=0,
        progress=0,
    )
    defaults.update(kwargs)
    task = TestTask(**defaults)
    db.add(task)
    db.flush()
    return task


def _create_case(db, testUser, **kwargs):
    project = Project(
        name=f"vis_case_proj_{int(time.time()*1000)}",
        user_id=testUser.id,
        description="test",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    ts = int(time.time() * 1000)
    defaults = dict(
        case_no=f"VC{ts}",
        project_id=project.id,
        module="测试模块",
        title="vis_test_case",
        precondition="无",
        steps_json=[{"step": "1", "action": "打开", "param": ""}],
        expected_result="成功",
        priority=2,
        case_type="UI",
    )
    defaults.update(kwargs)
    case = TestCase(**defaults)
    db.add(case)
    db.flush()
    return case


class TestVisibilityConfigPermissionMixin:
    def test_check_permission_owner(self, db, testUser):
        mixin = VisibilityConfigPermissionMixin()
        project = Project(
            name="perm_test_project",
            user_id=testUser.id,
            description="test",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()
        result = mixin.check_permission(db, testUser.id, project.id)
        assert result is True

    def test_check_permission_not_owner(self, db, testUser):
        mixin = VisibilityConfigPermissionMixin()
        project = Project(
            name="perm_test_project2",
            user_id=testUser.id,
            description="test",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()
        result = mixin.check_permission(db, 99999, project.id)
        assert result is False

    def test_check_permission_archived_project(self, db, testUser):
        mixin = VisibilityConfigPermissionMixin()
        project = Project(
            name="perm_test_project3",
            user_id=testUser.id,
            description="test",
            status=0,
            project_type="web",
        )
        db.add(project)
        db.flush()
        result = mixin.check_permission(db, testUser.id, project.id)
        assert result is False

    def test_check_permission_nonexistent_project(self, db):
        mixin = VisibilityConfigPermissionMixin()
        result = mixin.check_permission(db, 1, 99999)
        assert result is False


class TestVisibilityConfigCoreMixin:
    def test_init_creates_directories(self, tmp_path):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
            assert mixin._global_config is None

    def test_get_global_config_default(self):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            config = mixin.get_global_config()
            assert isinstance(config, VisibilityConfig)

    def test_set_global_config(self):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        new_config = VisibilityConfig(headless=False, record_video=True)
        mixin.set_global_config(new_config)
        assert mixin._global_config.headless is False
        assert mixin._global_config.record_video is True

    def test_get_task_config_no_visibility(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            task = _create_task(db, testUser)
            config = mixin.get_task_config(task)
            assert isinstance(config, VisibilityConfig)

    def test_get_task_config_with_visibility(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            task = _create_task(db, testUser, visibility_config={"headless": False, "record_video": True})
            config = mixin.get_task_config(task)
            assert isinstance(config, VisibilityConfig)

    def test_get_task_config_invalid_visibility(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            task = _create_task(db, testUser, visibility_config="invalid_json")
            config = mixin.get_task_config(task)
            assert isinstance(config, VisibilityConfig)

    def test_get_project_config_no_project(self, db):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            config = mixin.get_project_config(db, 99999)
            assert isinstance(config, VisibilityConfig)

    def test_get_project_config_with_config(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            project = Project(
                name="vis_config_project",
                user_id=testUser.id,
                description="test",
                status=1,
                project_type="web",
                config={"visibility_config": {"headless": False}},
            )
            db.add(project)
            db.flush()
            config = mixin.get_project_config(db, project.id)
            assert isinstance(config, VisibilityConfig)

    def test_get_project_config_invalid_config(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            project = Project(
                name="vis_config_project2",
                user_id=testUser.id,
                description="test",
                status=1,
                project_type="web",
                config={"visibility_config": "not_a_dict"},
            )
            db.add(project)
            db.flush()
            config = mixin.get_project_config(db, project.id)
            assert isinstance(config, VisibilityConfig)

    def test_get_case_config_no_visibility(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            case = _create_case(db, testUser)
            config = mixin.get_case_config(case)
            assert isinstance(config, VisibilityConfig)

    def test_get_case_config_with_task_and_visibility(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        with patch.object(VisibilityEnvLoader, "load_from_env", return_value=VisibilityConfig()):
            task = _create_task(db, testUser, visibility_config={"record_video": True})
            case = _create_case(db, testUser, visibility_config={"headless": False})
            config = mixin.get_case_config(case, task)
            assert isinstance(config, VisibilityConfig)

    def test_update_task_config(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        task = _create_task(db, testUser)
        new_config = VisibilityConfig(headless=False)
        mixin.update_task_config(task, new_config)
        assert task.visibility_config is not None

    def test_update_case_config(self, db, testUser):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        case = _create_case(db, testUser)
        new_config = VisibilityConfig(headless=False)
        mixin.update_case_config(case, new_config)
        assert case.visibility_config is not None

    def test_get_video_save_path(self):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        path = mixin.get_video_save_path(1, 2)
        assert "task_1_case_2" in str(path)
        assert str(path).endswith(".webm")

    def test_get_screenshot_save_path(self):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        path = mixin.get_screenshot_save_path(1, 2, 3)
        assert "task_1_case_2_step_3" in str(path)
        assert str(path).endswith(".png")

    def test_validate_config(self):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        config = VisibilityConfig()
        valid, msg = mixin.validate_config(config)
        assert isinstance(valid, bool)
        assert isinstance(msg, str)

    def test_get_config_summary(self):
        with patch.object(VisibilityConfigCoreMixin, "_ensure_directories"):
            mixin = VisibilityConfigCoreMixin()
        config = VisibilityConfig()
        summary = mixin.get_config_summary(config)
        assert isinstance(summary, str)
