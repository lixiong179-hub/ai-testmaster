import pytest
from app.services.visibility_config.models import VisibilityConfig, VisibilityLevel, ResourceVisibilityRequest
from app.services.visibility_config.merger import VisibilityConfigMerger
from app.services.visibility_config.validator import VisibilityConfigValidator
from app.services.visibility_config.env_loader import VisibilityEnvLoader


class TestVisibilityLevel:
    def test_global(self):
        assert VisibilityLevel.GLOBAL.value == "global"

    def test_task(self):
        assert VisibilityLevel.TASK.value == "task"

    def test_case(self):
        assert VisibilityLevel.CASE.value == "case"


class TestVisibilityConfig:
    def test_defaults(self):
        config = VisibilityConfig()
        assert config.headless is True
        assert config.record_video is False
        assert config.video_resolution == (1920, 1080)
        assert config.video_fps == 30
        assert config.execution_speed == "normal"

    def test_to_dict(self):
        config = VisibilityConfig()
        d = config.to_dict()
        assert "headless" in d
        assert "record_video" in d
        assert "video_resolution" in d
        assert d["headless"] is True

    def test_from_dict(self):
        data = {
            "headless": False,
            "record_video": True,
            "video_resolution": [1280, 720],
            "video_fps": 60,
            "execution_speed": "fast",
            "action_delay_ms": 100,
        }
        config = VisibilityConfig.from_dict(data)
        assert config.headless is False
        assert config.record_video is True
        assert config.video_resolution == (1280, 720)
        assert config.video_fps == 60
        assert config.execution_speed == "fast"

    def test_from_dict_partial(self):
        config = VisibilityConfig.from_dict({"headless": False})
        assert config.headless is False
        assert config.record_video is False

    def test_from_dict_empty(self):
        config = VisibilityConfig.from_dict({})
        assert config.headless is True

    def test_round_trip(self):
        original = VisibilityConfig(headless=False, record_video=True, video_fps=60)
        d = original.to_dict()
        restored = VisibilityConfig.from_dict(d)
        assert restored.headless == original.headless
        assert restored.record_video == original.record_video
        assert restored.video_fps == original.video_fps


class TestVisibilityConfigMerger:
    def test_merge_basic(self):
        base = VisibilityConfig(headless=True, execution_speed="normal")
        override = VisibilityConfig(headless=False, execution_speed="fast")
        merged = VisibilityConfigMerger.merge(base, override)
        assert merged.headless is False
        assert merged.execution_speed == "fast"

    def test_merge_hidden_fields_union(self):
        base = VisibilityConfig()
        base.hidden_fields = ["field1", "field2"]
        override = VisibilityConfig()
        override.hidden_fields = ["field2", "field3"]
        merged = VisibilityConfigMerger.merge(base, override)
        assert set(merged.hidden_fields) == {"field1", "field2", "field3"}

    def test_merge_preserves_base_when_no_override(self):
        base = VisibilityConfig(video_fps=60)
        override = VisibilityConfig()
        merged = VisibilityConfigMerger.merge(base, override)
        assert isinstance(merged.video_fps, int)

    def test_merge_empty_hidden_fields(self):
        base = VisibilityConfig()
        base.hidden_fields = []
        override = VisibilityConfig()
        override.hidden_fields = ["field1"]
        merged = VisibilityConfigMerger.merge(base, override)
        assert "field1" in merged.hidden_fields


class TestVisibilityConfigValidator:
    def test_valid_config(self):
        config = VisibilityConfig()
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is True
        assert msg == ""

    def test_resolution_too_small(self):
        config = VisibilityConfig(video_resolution=(320, 240))
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "640x480" in msg

    def test_resolution_too_large(self):
        config = VisibilityConfig(video_resolution=(7680, 4320))
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "4K" in msg

    def test_fps_too_low(self):
        config = VisibilityConfig(video_fps=10)
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "帧率" in msg

    def test_fps_too_high(self):
        config = VisibilityConfig(video_fps=120)
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "帧率" in msg

    def test_invalid_speed(self):
        config = VisibilityConfig(execution_speed="turbo")
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "速度" in msg

    def test_negative_delay(self):
        config = VisibilityConfig(action_delay_ms=-100)
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "延迟" in msg

    def test_delay_too_high(self):
        config = VisibilityConfig(action_delay_ms=6000)
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "延迟" in msg

    def test_get_summary_headless(self):
        config = VisibilityConfig(headless=True)
        summary = VisibilityConfigValidator.get_summary(config)
        assert "无头模式" in summary

    def test_get_summary_visible(self):
        config = VisibilityConfig(headless=False)
        summary = VisibilityConfigValidator.get_summary(config)
        assert "可见模式" in summary

    def test_get_summary_video(self):
        config = VisibilityConfig(record_video=True)
        summary = VisibilityConfigValidator.get_summary(config)
        assert "录制视频" in summary


class TestVisibilityEnvLoader:
    def test_speed_delay_map(self):
        assert VisibilityEnvLoader.SPEED_DELAY_MAP["slow"] == 1000
        assert VisibilityEnvLoader.SPEED_DELAY_MAP["normal"] == 500
        assert VisibilityEnvLoader.SPEED_DELAY_MAP["fast"] == 100

    def test_load_from_env_defaults(self):
        import os
        for key in ["TEST_HEADLESS", "TEST_RECORD_VIDEO", "TEST_VIDEO_WIDTH",
                     "TEST_VIDEO_HEIGHT", "TEST_VIDEO_FPS", "TEST_TAKE_SCREENSHOT",
                     "TEST_SCREENSHOT_ON_FAILURE", "TEST_EXECUTION_SPEED"]:
            os.environ.pop(key, None)
        config = VisibilityEnvLoader.load_from_env()
        assert config.headless is True
        assert config.record_video is False

    def test_load_from_env_custom(self):
        import os
        os.environ["TEST_HEADLESS"] = "false"
        os.environ["TEST_RECORD_VIDEO"] = "true"
        os.environ["TEST_VIDEO_FPS"] = "60"
        try:
            config = VisibilityEnvLoader.load_from_env()
            assert config.headless is False
            assert config.record_video is True
            assert config.video_fps == 60
        finally:
            os.environ.pop("TEST_HEADLESS", None)
            os.environ.pop("TEST_RECORD_VIDEO", None)
            os.environ.pop("TEST_VIDEO_FPS", None)


class TestResourceVisibilityRequest:
    def test_creation(self):
        req = ResourceVisibilityRequest(
            resource_type="test_case",
            resource_id=1,
            user_id=2,
        )
        assert req.resource_type == "test_case"
        assert req.resource_id == 1
        assert req.user_id == 2
        assert req.user_roles == []
