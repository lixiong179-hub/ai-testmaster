import pytest
from app.services.execution_mode_types import (
    ExecutionMode,
    ExecutionStrategy,
    StrategyConfig,
    ExecutionConfig,
)


class TestExecutionMode:
    def test_values(self):
        assert ExecutionMode.AI_VISION.value == "ai_vision"
        assert ExecutionMode.API.value == "api"
        assert ExecutionMode.UNKNOWN.value == "unknown"


class TestExecutionStrategy:
    def test_values(self):
        assert ExecutionStrategy.STRICT.value == "strict"
        assert ExecutionStrategy.SMART.value == "smart"
        assert ExecutionStrategy.FAST.value == "fast"


class TestStrategyConfig:
    def test_defaults(self):
        config = StrategyConfig()
        assert config.use_css_selector is True
        assert config.confidence_threshold == 0.9
        assert config.max_retries == 1

    def test_custom_values(self):
        config = StrategyConfig(max_retries=5, confidence_threshold=0.99)
        assert config.max_retries == 5
        assert config.confidence_threshold == 0.99


class TestExecutionConfig:
    def test_defaults(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION)
        assert config.strategy == ExecutionStrategy.SMART
        assert config.headless is True
        assert config.record_video is False
        assert config.video_path is None

    def test_is_ai_vision(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION)
        assert config.is_ai_vision() is True
        assert config.is_api() is False

    def test_is_api(self):
        config = ExecutionConfig(mode=ExecutionMode.API)
        assert config.is_api() is True
        assert config.is_ai_vision() is False

    def test_is_strict_mode(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.STRICT)
        assert config.is_strict_mode() is True
        assert config.is_smart_mode() is False

    def test_is_smart_mode(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.SMART)
        assert config.is_smart_mode() is True

    def test_is_fast_mode(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.FAST)
        assert config.is_fast_mode() is True

    def test_with_video_path(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, video_path="/tmp/video.mp4")
        assert config.video_path == "/tmp/video.mp4"
