import pytest
from app.services.execution_mode_selector import ExecutionModeSelector, get_execution_mode_selector
from app.services.execution_mode_types import ExecutionMode, ExecutionStrategy


class TestSelectMode:
    def test_ui_automation_maps_to_ai_vision(self):
        assert ExecutionModeSelector.select_mode("ui_automation") == ExecutionMode.AI_VISION

    def test_ui_uppercase(self):
        assert ExecutionModeSelector.select_mode("UI") == ExecutionMode.AI_VISION

    def test_functional(self):
        assert ExecutionModeSelector.select_mode("functional") == ExecutionMode.AI_VISION

    def test_api_automation_maps_to_api(self):
        assert ExecutionModeSelector.select_mode("api_automation") == ExecutionMode.API

    def test_api_uppercase(self):
        assert ExecutionModeSelector.select_mode("API") == ExecutionMode.API

    def test_performance_maps_to_unknown(self):
        assert ExecutionModeSelector.select_mode("performance") == ExecutionMode.UNKNOWN

    def test_security_maps_to_unknown(self):
        assert ExecutionModeSelector.select_mode("security") == ExecutionMode.UNKNOWN

    def test_empty_string_defaults_to_ai_vision(self):
        assert ExecutionModeSelector.select_mode("") == ExecutionMode.AI_VISION

    def test_unknown_type_defaults_to_ai_vision(self):
        assert ExecutionModeSelector.select_mode("nonexistent") == ExecutionMode.AI_VISION

    def test_chinese_functional(self):
        assert ExecutionModeSelector.select_mode("功能") == ExecutionMode.AI_VISION

    def test_chinese_api(self):
        assert ExecutionModeSelector.select_mode("接口") == ExecutionMode.API


class TestSelectStrategy:
    def test_strict(self):
        assert ExecutionModeSelector.select_strategy("strict") == ExecutionStrategy.STRICT

    def test_smart(self):
        assert ExecutionModeSelector.select_strategy("smart") == ExecutionStrategy.SMART

    def test_fast(self):
        assert ExecutionModeSelector.select_strategy("fast") == ExecutionStrategy.FAST

    def test_none_defaults_to_smart(self):
        assert ExecutionModeSelector.select_strategy(None) == ExecutionStrategy.SMART

    def test_empty_defaults_to_smart(self):
        assert ExecutionModeSelector.select_strategy("") == ExecutionStrategy.SMART

    def test_unknown_defaults_to_smart(self):
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
        assert config.enable_batch_recognition is True


class TestGetExecutionConfig:
    def test_default_config(self):
        config = ExecutionModeSelector.get_execution_config("ui_automation")
        assert config.mode == ExecutionMode.AI_VISION
        assert config.strategy == ExecutionStrategy.SMART
        assert config.headless is True
        assert config.record_video is False

    def test_global_strategy_override(self):
        config = ExecutionModeSelector.get_execution_config("ui_automation", global_strategy="fast")
        assert config.strategy == ExecutionStrategy.FAST

    def test_task_strategy_overrides_global(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation", global_strategy="fast", task_strategy="strict"
        )
        assert config.strategy == ExecutionStrategy.STRICT

    def test_case_strategy_overrides_task(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation", task_strategy="fast", case_strategy="smart"
        )
        assert config.strategy == ExecutionStrategy.SMART

    def test_headless_override(self):
        config = ExecutionModeSelector.get_execution_config("ui_automation", global_headless=False)
        assert config.headless is False

    def test_task_headless_overrides_global(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation", global_headless=False, task_headless=True
        )
        assert config.headless is True

    def test_case_headless_overrides_task(self):
        config = ExecutionModeSelector.get_execution_config(
            "ui_automation", task_headless=True, case_headless=False
        )
        assert config.headless is False

    def test_record_video_override(self):
        config = ExecutionModeSelector.get_execution_config("ui_automation", global_record_video=True)
        assert config.record_video is True

    def test_video_path(self):
        config = ExecutionModeSelector.get_execution_config("ui_automation", video_path="/tmp/video.mp4")
        assert config.video_path == "/tmp/video.mp4"

    def test_api_mode(self):
        config = ExecutionModeSelector.get_execution_config("api_automation")
        assert config.mode == ExecutionMode.API


class TestIsAiVisionCase:
    def test_ui_type(self):
        assert ExecutionModeSelector.is_ai_vision_case("ui_automation") is True

    def test_api_type(self):
        assert ExecutionModeSelector.is_ai_vision_case("api_automation") is False


class TestIsApiCase:
    def test_api_type(self):
        assert ExecutionModeSelector.is_api_case("api_automation") is True

    def test_ui_type(self):
        assert ExecutionModeSelector.is_api_case("ui_automation") is False


class TestGetExecutionModeSelector:
    def test_returns_instance(self):
        selector = get_execution_mode_selector()
        assert isinstance(selector, ExecutionModeSelector)
