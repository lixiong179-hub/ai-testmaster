import pytest
from app.services.visibility_config.core_mixin import VisibilityConfigCoreMixin
from app.services.visibility_config.models import VisibilityConfig


class TestVisibilityConfigCoreMixin:
    def setup_method(self):
        self.mixin = VisibilityConfigCoreMixin()

    def test_get_global_config_default(self):
        config = self.mixin.get_global_config()
        assert isinstance(config, VisibilityConfig)

    def test_set_global_config(self):
        new_config = VisibilityConfig(headless=False, record_video=True)
        self.mixin.set_global_config(new_config)
        result = self.mixin.get_global_config()
        assert result.headless is False
        assert result.record_video is True

    def test_get_video_save_path(self):
        path = self.mixin.get_video_save_path(task_id=1, case_id=2)
        assert "task_1_case_2" in str(path)
        assert str(path).endswith(".webm")

    def test_get_screenshot_save_path(self):
        path = self.mixin.get_screenshot_save_path(task_id=1, case_id=2, step_number=3)
        assert "task_1_case_2_step_3" in str(path)
        assert str(path).endswith(".png")

    def test_validate_config(self):
        config = VisibilityConfig()
        valid, msg = self.mixin.validate_config(config)
        assert valid is True

    def test_get_config_summary(self):
        config = VisibilityConfig(headless=True)
        summary = self.mixin.get_config_summary(config)
        assert "无头模式" in summary

    def test_get_task_config_no_vis_config(self):
        class FakeTask:
            visibility_config = None
        task = FakeTask()
        config = self.mixin.get_task_config(task)
        assert isinstance(config, VisibilityConfig)

    def test_get_task_config_with_vis_config(self):
        class FakeTask:
            visibility_config = {"headless": False, "record_video": True}
        task = FakeTask()
        config = self.mixin.get_task_config(task)
        assert config.headless is False

    def test_get_case_config_no_vis_config(self):
        class FakeCase:
            visibility_config = None
        case = FakeCase()
        config = self.mixin.get_case_config(case)
        assert isinstance(config, VisibilityConfig)

    def test_get_case_config_with_vis_config(self):
        class FakeCase:
            visibility_config = {"headless": False}
        case = FakeCase()
        config = self.mixin.get_case_config(case)
        assert config.headless is False

    def test_update_task_config(self):
        class FakeTask:
            id = 1
            visibility_config = None
        task = FakeTask()
        new_config = VisibilityConfig(headless=False)
        self.mixin.update_task_config(task, new_config)
        assert task.visibility_config is not None
        assert task.visibility_config["headless"] is False

    def test_update_case_config(self):
        class FakeCase:
            id = 1
            visibility_config = None
        case = FakeCase()
        new_config = VisibilityConfig(headless=False)
        self.mixin.update_case_config(case, new_config)
        assert case.visibility_config is not None
        assert case.visibility_config["headless"] is False

    def test_get_project_config_nonexistent(self, db):
        config = self.mixin.get_project_config(db, 99999)
        assert isinstance(config, VisibilityConfig)
