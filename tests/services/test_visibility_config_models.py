import pytest
from app.services.visibility_config.models import VisibilityConfig, VisibilityLevel, ResourceVisibilityRequest


class TestVisibilityConfig:
    def test_default_values(self):
        config = VisibilityConfig()
        assert config.headless is True
        assert config.record_video is False
        assert config.video_resolution == (1920, 1080)
        assert config.video_fps == 30
        assert config.take_screenshot is True
        assert config.execution_speed == "normal"
        assert config.action_delay_ms == 500
        assert config.highlight_elements is True
        assert config.hidden_fields == []

    def test_to_dict(self):
        config = VisibilityConfig()
        d = config.to_dict()
        assert "headless" in d
        assert "record_video" in d
        assert "video_resolution" in d
        assert d["headless"] is True

    def test_from_dict_full(self):
        data = {
            "headless": False,
            "record_video": True,
            "video_resolution": [1280, 720],
            "video_fps": 24,
            "take_screenshot": False,
            "screenshot_on_failure": False,
            "screenshot_on_success": True,
            "execution_speed": "fast",
            "action_delay_ms": 100,
            "highlight_elements": False,
            "show_ai_analysis": False,
            "hidden_fields": ["password"],
        }
        config = VisibilityConfig.from_dict(data)
        assert config.headless is False
        assert config.record_video is True
        assert config.video_resolution == (1280, 720)
        assert config.video_fps == 24
        assert config.execution_speed == "fast"
        assert config.hidden_fields == ["password"]

    def test_from_dict_partial(self):
        data = {"headless": False}
        config = VisibilityConfig.from_dict(data)
        assert config.headless is False
        assert config.record_video is False

    def test_from_dict_empty(self):
        config = VisibilityConfig.from_dict({})
        assert config.headless is True

    def test_roundtrip(self):
        config = VisibilityConfig(headless=False, record_video=True, execution_speed="slow")
        d = config.to_dict()
        restored = VisibilityConfig.from_dict(d)
        assert restored.headless == config.headless
        assert restored.record_video == config.record_video
        assert restored.execution_speed == config.execution_speed


class TestVisibilityLevel:
    def test_values(self):
        assert VisibilityLevel.GLOBAL.value == "global"
        assert VisibilityLevel.TASK.value == "task"
        assert VisibilityLevel.CASE.value == "case"


class TestResourceVisibilityRequest:
    def test_create(self):
        req = ResourceVisibilityRequest(
            resource_type="test_case", resource_id=1, user_id=1,
        )
        assert req.resource_type == "test_case"
        assert req.user_roles == []
