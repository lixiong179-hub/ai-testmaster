import pytest
import os
from app.services.visibility_config.merger import VisibilityConfigMerger
from app.services.visibility_config.env_loader import VisibilityEnvLoader
from app.services.visibility_config.models import VisibilityConfig


class TestVisibilityConfigMerger:
    def test_merge_override_bool(self):
        base = VisibilityConfig(headless=True)
        override = VisibilityConfig(headless=False)
        merged = VisibilityConfigMerger.merge(base, override)
        assert merged.headless is False

    def test_merge_keeps_base_when_no_override(self):
        base = VisibilityConfig(headless=True)
        override = VisibilityConfig()
        merged = VisibilityConfigMerger.merge(base, override)
        assert merged.headless is True

    def test_merge_hidden_fields_union(self):
        base = VisibilityConfig(hidden_fields=["password"])
        override = VisibilityConfig(hidden_fields=["token"])
        merged = VisibilityConfigMerger.merge(base, override)
        assert "password" in merged.hidden_fields
        assert "token" in merged.hidden_fields

    def test_merge_empty_hidden_fields(self):
        base = VisibilityConfig(hidden_fields=[])
        override = VisibilityConfig(hidden_fields=[])
        merged = VisibilityConfigMerger.merge(base, override)
        assert merged.hidden_fields == []

    def test_merge_resolution(self):
        base = VisibilityConfig(video_resolution=(1920, 1080))
        override = VisibilityConfig(video_resolution=(1280, 720))
        merged = VisibilityConfigMerger.merge(base, override)
        assert merged.video_resolution == (1280, 720)


class TestVisibilityEnvLoader:
    def test_default_values(self):
        for key in ["TEST_HEADLESS", "TEST_RECORD_VIDEO", "TEST_VIDEO_WIDTH",
                     "TEST_VIDEO_HEIGHT", "TEST_VIDEO_FPS", "TEST_TAKE_SCREENSHOT",
                     "TEST_SCREENSHOT_ON_FAILURE", "TEST_EXECUTION_SPEED"]:
            os.environ.pop(key, None)
        config = VisibilityEnvLoader.load_from_env()
        assert config.headless is True
        assert config.record_video is False
        assert config.video_resolution == (1920, 1080)

    def test_headless_false(self):
        os.environ["TEST_HEADLESS"] = "false"
        try:
            config = VisibilityEnvLoader.load_from_env()
            assert config.headless is False
        finally:
            del os.environ["TEST_HEADLESS"]

    def test_record_video_true(self):
        os.environ["TEST_RECORD_VIDEO"] = "true"
        try:
            config = VisibilityEnvLoader.load_from_env()
            assert config.record_video is True
        finally:
            del os.environ["TEST_RECORD_VIDEO"]

    def test_custom_resolution(self):
        os.environ["TEST_VIDEO_WIDTH"] = "1280"
        os.environ["TEST_VIDEO_HEIGHT"] = "720"
        try:
            config = VisibilityEnvLoader.load_from_env()
            assert config.video_resolution == (1280, 720)
        finally:
            del os.environ["TEST_VIDEO_WIDTH"]
            del os.environ["TEST_VIDEO_HEIGHT"]

    def test_speed_delay_map(self):
        assert VisibilityEnvLoader.SPEED_DELAY_MAP["slow"] == 1000
        assert VisibilityEnvLoader.SPEED_DELAY_MAP["normal"] == 500
        assert VisibilityEnvLoader.SPEED_DELAY_MAP["fast"] == 100

    def test_execution_speed_from_env(self):
        os.environ["TEST_EXECUTION_SPEED"] = "fast"
        try:
            config = VisibilityEnvLoader.load_from_env()
            assert config.execution_speed == "fast"
            assert config.action_delay_ms == 100
        finally:
            del os.environ["TEST_EXECUTION_SPEED"]
