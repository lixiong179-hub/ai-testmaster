import pytest
from app.services.execution_mode_selector import ExecutionModeSelector, get_execution_mode_selector
from app.services.execution_mode_types import (
    ExecutionMode,
    ExecutionStrategy,
    StrategyConfig,
    ExecutionConfig,
)


class TestExecutionModeSelector:
    def test_select_mode_ui_automation(self):
        assert ExecutionModeSelector.select_mode("ui_automation") == ExecutionMode.AI_VISION

    def test_select_mode_ui(self):
        assert ExecutionModeSelector.select_mode("UI") == ExecutionMode.AI_VISION

    def test_select_mode_functional(self):
        assert ExecutionModeSelector.select_mode("functional") == ExecutionMode.AI_VISION

    def test_select_mode_manual(self):
        assert ExecutionModeSelector.select_mode("manual") == ExecutionMode.AI_VISION

    def test_select_mode_api_automation(self):
        assert ExecutionModeSelector.select_mode("api_automation") == ExecutionMode.API

    def test_select_mode_api(self):
        assert ExecutionModeSelector.select_mode("API") == ExecutionMode.API

    def test_select_mode_performance(self):
        assert ExecutionModeSelector.select_mode("performance") == ExecutionMode.UNKNOWN

    def test_select_mode_security(self):
        assert ExecutionModeSelector.select_mode("security") == ExecutionMode.UNKNOWN

    def test_select_mode_empty(self):
        assert ExecutionModeSelector.select_mode("") == ExecutionMode.AI_VISION

    def test_select_mode_unknown(self):
        assert ExecutionModeSelector.select_mode("unknown_type") == ExecutionMode.AI_VISION

    def test_select_mode_chinese_functional(self):
        assert ExecutionModeSelector.select_mode("功能") == ExecutionMode.AI_VISION

    def test_select_mode_chinese_api(self):
        assert ExecutionModeSelector.select_mode("接口") == ExecutionMode.API


class TestSelectStrategy:
    def test_strict(self):
        assert ExecutionModeSelector.select_strategy("strict") == ExecutionStrategy.STRICT

    def test_smart(self):
        assert ExecutionModeSelector.select_strategy("smart") == ExecutionStrategy.SMART

    def test_fast(self):
        assert ExecutionModeSelector.select_strategy("fast") == ExecutionStrategy.FAST

    def test_none_returns_smart(self):
        assert ExecutionModeSelector.select_strategy(None) == ExecutionStrategy.SMART

    def test_empty_returns_smart(self):
        assert ExecutionModeSelector.select_strategy("") == ExecutionStrategy.SMART

    def test_unknown_returns_smart(self):
        assert ExecutionModeSelector.select_strategy("unknown") == ExecutionStrategy.SMART

    def test_case_insensitive(self):
        assert ExecutionModeSelector.select_strategy("STRICT") == ExecutionStrategy.STRICT


class TestGetStrategyConfig:
    def test_strict_config(self):
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.STRICT)
        assert config.confidence_threshold == 0.95
        assert config.max_retries == 3
        assert config.enable_batch_recognition is False

    def test_smart_config(self):
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.SMART)
        assert config.confidence_threshold == 0.9
        assert config.max_retries == 1
        assert config.enable_batch_recognition is True

    def test_fast_config(self):
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.FAST)
        assert config.confidence_threshold == 0.85
        assert config.max_retries == 0
        assert config.use_xpath is False


class TestGetExecutionConfig:
    def test_default_config(self):
        config = ExecutionModeSelector.get_execution_config("ui_automation")
        assert config.mode == ExecutionMode.AI_VISION
        assert config.strategy == ExecutionStrategy.SMART
        assert config.headless is True
        assert config.record_video is False

    def test_global_override(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation",
            global_headless=False,
            global_record_video=True,
            global_strategy="fast",
        )
        assert config.headless is False
        assert config.record_video is True
        assert config.strategy == ExecutionStrategy.FAST

    def test_task_override(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation",
            global_headless=False,
            task_headless=True,
        )
        assert config.headless is True

    def test_case_override(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation",
            global_headless=False,
            task_headless=True,
            case_headless=False,
        )
        assert config.headless is False

    def test_strategy_override_priority(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation",
            global_strategy="strict",
            task_strategy="fast",
            case_strategy="smart",
        )
        assert config.strategy == ExecutionStrategy.SMART

    def test_api_mode(self):
        config = ExecutionModeSelector.get_execution_config("api_automation")
        assert config.mode == ExecutionMode.API

    def test_video_path(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation",
            video_path="/tmp/video.mp4",
        )
        assert config.video_path == "/tmp/video.mp4"


class TestIsAiVisionCase:
    def test_ui_type(self):
        assert ExecutionModeSelector.is_ai_vision_case("ui_automation") is True

    def test_api_type(self):
        assert ExecutionModeSelector.is_ai_vision_case("api_automation") is False

    def test_performance_type(self):
        assert ExecutionModeSelector.is_ai_vision_case("performance") is False


class TestIsApiCase:
    def test_api_type(self):
        assert ExecutionModeSelector.is_api_case("api_automation") is True

    def test_ui_type(self):
        assert ExecutionModeSelector.is_api_case("ui_automation") is False


class TestGetExecutionModeSelector:
    def test_returns_instance(self):
        selector = get_execution_mode_selector()
        assert isinstance(selector, ExecutionModeSelector)


class TestExecutionConfig:
    def test_is_ai_vision(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION)
        assert config.is_ai_vision() is True

    def test_is_api(self):
        config = ExecutionConfig(mode=ExecutionMode.API)
        assert config.is_api() is True

    def test_is_strict_mode(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.STRICT)
        assert config.is_strict_mode() is True

    def test_is_smart_mode(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.SMART)
        assert config.is_smart_mode() is True

    def test_is_fast_mode(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.FAST)
        assert config.is_fast_mode() is True

    def test_default_strategy(self):
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION)
        assert config.strategy == ExecutionStrategy.SMART
