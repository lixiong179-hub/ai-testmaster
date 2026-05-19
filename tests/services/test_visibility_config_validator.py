import pytest
from app.services.visibility_config.validator import VisibilityConfigValidator
from app.services.visibility_config.models import VisibilityConfig


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

    def test_invalid_execution_speed(self):
        config = VisibilityConfig(execution_speed="turbo")
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "执行速度" in msg

    def test_negative_action_delay(self):
        config = VisibilityConfig(action_delay_ms=-1)
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "延迟" in msg

    def test_action_delay_too_high(self):
        config = VisibilityConfig(action_delay_ms=6000)
        valid, msg = VisibilityConfigValidator.validate(config)
        assert valid is False
        assert "延迟" in msg

    def test_valid_boundary_fps(self):
        config = VisibilityConfig(video_fps=15)
        valid, _ = VisibilityConfigValidator.validate(config)
        assert valid is True

    def test_valid_boundary_resolution(self):
        config = VisibilityConfig(video_resolution=(640, 480))
        valid, _ = VisibilityConfigValidator.validate(config)
        assert valid is True


class TestGetSummary:
    def test_headless_summary(self):
        config = VisibilityConfig(headless=True)
        summary = VisibilityConfigValidator.get_summary(config)
        assert "无头模式" in summary

    def test_visible_summary(self):
        config = VisibilityConfig(headless=False)
        summary = VisibilityConfigValidator.get_summary(config)
        assert "可见模式" in summary

    def test_video_summary(self):
        config = VisibilityConfig(record_video=True)
        summary = VisibilityConfigValidator.get_summary(config)
        assert "录制视频" in summary

    def test_speed_in_summary(self):
        config = VisibilityConfig(execution_speed="fast")
        summary = VisibilityConfigValidator.get_summary(config)
        assert "fast" in summary
