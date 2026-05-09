"""
ExecutionModeSelector 单元测试

测试范围:
- 执行模式选择
- 执行策略选择
- 配置合并
- 策略配置获取

要求: 不使用Mock，覆盖率>=95%
"""
import pytest
from typing import Optional

from app.services.execution_mode_selector import (
    ExecutionModeSelector,
    ExecutionMode,
    ExecutionStrategy,
    ExecutionConfig,
    StrategyConfig
)


class TestExecutionModeSelector:
    """ExecutionModeSelector 测试�?""
    
    def test_select_mode_ui_case(self):
        """测试UI用例类型选择"""
        mode = ExecutionModeSelector.select_mode("UI")
        assert mode == ExecutionMode.AI_VISION
        
        mode = ExecutionModeSelector.select_mode("ui")
        assert mode == ExecutionMode.AI_VISION
        
        mode = ExecutionModeSelector.select_mode("功能")
        assert mode == ExecutionMode.AI_VISION
        
        mode = ExecutionModeSelector.select_mode("功能测试")
        assert mode == ExecutionMode.AI_VISION
    
    def test_select_mode_api_case(self):
        """测试API用例类型选择"""
        mode = ExecutionModeSelector.select_mode("API")
        assert mode == ExecutionMode.API
        
        mode = ExecutionModeSelector.select_mode("api")
        assert mode == ExecutionMode.API
        
        mode = ExecutionModeSelector.select_mode("接口")
        assert mode == ExecutionMode.API
        
        mode = ExecutionModeSelector.select_mode("接口测试")
        assert mode == ExecutionMode.API
    
    def test_select_mode_empty(self):
        """测试空用例类型选择"""
        mode = ExecutionModeSelector.select_mode("")
        assert mode == ExecutionMode.AI_VISION  # 默认使用AI视觉模式
    
    def test_select_mode_unknown(self):
        """测试未知用例类型选择"""
        mode = ExecutionModeSelector.select_mode("unknown_type")
        assert mode == ExecutionMode.AI_VISION  # 默认使用AI视觉模式
    
    def test_select_mode_none(self):
        """测试None用例类型选择"""
        mode = ExecutionModeSelector.select_mode(None)
        assert mode == ExecutionMode.AI_VISION
    
    def test_is_ai_vision_case(self):
        """测试判断是否为AI视觉用例"""
        assert ExecutionModeSelector.is_ai_vision_case("UI") is True
        assert ExecutionModeSelector.is_ai_vision_case("功能") is True
        assert ExecutionModeSelector.is_ai_vision_case("API") is False
        assert ExecutionModeSelector.is_ai_vision_case("接口") is False
    
    def test_is_api_case(self):
        """测试判断是否为API用例"""
        assert ExecutionModeSelector.is_api_case("API") is True
        assert ExecutionModeSelector.is_api_case("接口") is True
        assert ExecutionModeSelector.is_api_case("UI") is False
        assert ExecutionModeSelector.is_api_case("功能") is False
    
    def test_select_strategy_strict(self):
        """测试选择严格策略"""
        strategy = ExecutionModeSelector.select_strategy("strict")
        assert strategy == ExecutionStrategy.STRICT
        
        strategy = ExecutionModeSelector.select_strategy("STRICT")
        assert strategy == ExecutionStrategy.STRICT
    
    def test_select_strategy_smart(self):
        """测试选择智能策略"""
        strategy = ExecutionModeSelector.select_strategy("smart")
        assert strategy == ExecutionStrategy.SMART
        
        strategy = ExecutionModeSelector.select_strategy("SMART")
        assert strategy == ExecutionStrategy.SMART
    
    def test_select_strategy_fast(self):
        """测试选择快速策�?""
        strategy = ExecutionModeSelector.select_strategy("fast")
        assert strategy == ExecutionStrategy.FAST
        
        strategy = ExecutionModeSelector.select_strategy("FAST")
        assert strategy == ExecutionStrategy.FAST
    
    def test_select_strategy_empty(self):
        """测试空策略选择"""
        strategy = ExecutionModeSelector.select_strategy("")
        assert strategy == ExecutionStrategy.SMART  # 默认使用智能模式
    
    def test_select_strategy_none(self):
        """测试None策略选择"""
        strategy = ExecutionModeSelector.select_strategy(None)
        assert strategy == ExecutionStrategy.SMART
    
    def test_select_strategy_unknown(self):
        """测试未知策略选择"""
        strategy = ExecutionModeSelector.select_strategy("unknown")
        assert strategy == ExecutionStrategy.SMART  # 默认使用智能模式
    
    def test_get_strategy_config_strict(self):
        """测试获取严格策略配置"""
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.STRICT)
        
        assert isinstance(config, StrategyConfig)
        assert config.use_css_selector is True
        assert config.use_xpath is True
        assert config.use_ai_vision is True
        assert config.max_retries == 3
        assert config.retry_delay == 2.0
        assert config.ai_timeout == 45
        assert config.confidence_threshold == 0.95
        assert config.use_locator_cache is True
        assert config.cache_ttl_minutes == 120
        assert config.enable_batch_recognition is False
        assert config.batch_size == 1
    
    def test_get_strategy_config_smart(self):
        """测试获取智能策略配置"""
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.SMART)
        
        assert isinstance(config, StrategyConfig)
        assert config.use_css_selector is True
        assert config.use_xpath is True
        assert config.use_ai_vision is True
        assert config.max_retries == 1
        assert config.retry_delay == 1.0
        assert config.ai_timeout == 30
        assert config.confidence_threshold == 0.9
        assert config.use_locator_cache is True
        assert config.cache_ttl_minutes == 60
        assert config.enable_batch_recognition is True
        assert config.batch_size == 5
    
    def test_get_strategy_config_fast(self):
        """测试获取快速策略配�?""
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.FAST)
        
        assert isinstance(config, StrategyConfig)
        assert config.use_css_selector is True
        assert config.use_xpath is False
        assert config.use_ai_vision is True
        assert config.max_retries == 0
        assert config.retry_delay == 0.0
        assert config.ai_timeout == 20
        assert config.confidence_threshold == 0.85
        assert config.use_locator_cache is False
        assert config.cache_ttl_minutes == 30
        assert config.enable_batch_recognition is True
        assert config.batch_size == 10
    
    def test_get_strategy_config_default(self):
        """测试获取默认策略配置（未知策略）"""
        # 使用一个不存在于STRATEGY_CONFIGS中的策略�?
        class FakeStrategy:
            value = "fake"
        
        config = ExecutionModeSelector.get_strategy_config(FakeStrategy())
        
        # 应该返回SMART配置作为默认
        assert isinstance(config, StrategyConfig)
        assert config.max_retries == 1  # SMART模式的配�?
    
    def test_get_execution_config_default(self):
        """测试获取默认执行配置"""
        config = ExecutionModeSelector.get_execution_config("UI")
        
        assert isinstance(config, ExecutionConfig)
        assert config.mode == ExecutionMode.AI_VISION
        assert config.strategy == ExecutionStrategy.SMART
        assert config.headless is True
        assert config.record_video is False
        assert config.strategy_config is not None
    
    def test_get_execution_config_with_strategy(self):
        """测试获取指定策略的执行配�?""
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            case_strategy="strict"
        )
        
        assert config.strategy == ExecutionStrategy.STRICT
        assert config.strategy_config.max_retries == 3
    
    def test_get_execution_config_strategy_priority(self):
        """测试策略配置的优先级：用例级 > 任务�?> 全局�?""
        # 用例级策略应该覆盖任务级和全局�?
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_strategy="fast",
            task_strategy="smart",
            case_strategy="strict"
        )
        
        assert config.strategy == ExecutionStrategy.STRICT
        
        # 任务级策略应该覆盖全局�?
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_strategy="fast",
            task_strategy="smart"
        )
        
        assert config.strategy == ExecutionStrategy.SMART
        
        # 只有全局级策�?
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_strategy="fast"
        )
        
        assert config.strategy == ExecutionStrategy.FAST
    
    def test_get_execution_config_headless_priority(self):
        """测试headless配置的优先级"""
        # 用例级应该覆盖任务级和全局�?
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_headless=False,
            task_headless=False,
            case_headless=True
        )
        
        assert config.headless is True
        
        # 任务级应该覆盖全局�?
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_headless=False,
            task_headless=True
        )
        
        assert config.headless is True
    
    def test_get_execution_config_record_video_priority(self):
        """测试record_video配置的优先级"""
        # 用例级应该覆盖任务级和全局�?
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_record_video=False,
            task_record_video=False,
            case_record_video=True
        )
        
        assert config.record_video is True
    
    def test_get_execution_config_with_video_path(self):
        """测试获取带视频路径的执行配置"""
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            video_path="/path/to/video.mp4"
        )
        
        assert config.video_path == "/path/to/video.mp4"
    
    def test_get_execution_config_api_mode(self):
        """测试API模式的执行配�?""
        config = ExecutionModeSelector.get_execution_config("API")
        
        assert config.mode == ExecutionMode.API
        assert config.is_api() is True
        assert config.is_ai_vision() is False


class TestExecutionConfig:
    """ExecutionConfig 测试�?""
    
    def test_execution_config_creation(self):
        """测试 ExecutionConfig 创建"""
        config = ExecutionConfig(
            mode=ExecutionMode.AI_VISION,
            strategy=ExecutionStrategy.SMART,
            headless=True,
            record_video=False
        )
        
        assert config.mode == ExecutionMode.AI_VISION
        assert config.strategy == ExecutionStrategy.SMART
        assert config.headless is True
        assert config.record_video is False
    
    def test_is_ai_vision(self):
        """测试 is_ai_vision 方法"""
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION)
        assert config.is_ai_vision() is True
        
        config = ExecutionConfig(mode=ExecutionMode.API)
        assert config.is_ai_vision() is False
    
    def test_is_api(self):
        """测试 is_api 方法"""
        config = ExecutionConfig(mode=ExecutionMode.API)
        assert config.is_api() is True
        
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION)
        assert config.is_api() is False
    
    def test_is_strict_mode(self):
        """测试 is_strict_mode 方法"""
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.STRICT)
        assert config.is_strict_mode() is True
        assert config.is_smart_mode() is False
        assert config.is_fast_mode() is False
    
    def test_is_smart_mode(self):
        """测试 is_smart_mode 方法"""
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.SMART)
        assert config.is_smart_mode() is True
        assert config.is_strict_mode() is False
        assert config.is_fast_mode() is False
    
    def test_is_fast_mode(self):
        """测试 is_fast_mode 方法"""
        config = ExecutionConfig(mode=ExecutionMode.AI_VISION, strategy=ExecutionStrategy.FAST)
        assert config.is_fast_mode() is True
        assert config.is_strict_mode() is False
        assert config.is_smart_mode() is False


class TestStrategyConfig:
    """StrategyConfig 测试�?""
    
    def test_strategy_config_default(self):
        """测试 StrategyConfig 默认�?""
        config = StrategyConfig()
        
        assert config.use_css_selector is True
        assert config.use_xpath is True
        assert config.use_ai_vision is True
        assert config.max_retries == 1
        assert config.retry_delay == 1.0
        assert config.ai_timeout == 30
        assert config.confidence_threshold == 0.9
        assert config.use_locator_cache is True
        assert config.cache_ttl_minutes == 60
        assert config.enable_batch_recognition is False
        assert config.batch_size == 5
    
    def test_strategy_config_custom(self):
        """测试 StrategyConfig 自定义�?""
        config = StrategyConfig(
            use_css_selector=False,
            use_xpath=False,
            use_ai_vision=False,
            max_retries=5,
            retry_delay=3.0,
            ai_timeout=60,
            confidence_threshold=0.99,
            use_locator_cache=False,
            cache_ttl_minutes=120,
            enable_batch_recognition=True,
            batch_size=20
        )
        
        assert config.use_css_selector is False
        assert config.use_xpath is False
        assert config.use_ai_vision is False
        assert config.max_retries == 5
        assert config.retry_delay == 3.0
        assert config.ai_timeout == 60
        assert config.confidence_threshold == 0.99
        assert config.use_locator_cache is False
        assert config.cache_ttl_minutes == 120
        assert config.enable_batch_recognition is True
        assert config.batch_size == 20


class TestExecutionModeEnum:
    """ExecutionMode 枚举测试�?""
    
    def test_execution_mode_values(self):
        """测试 ExecutionMode 枚举�?""
        assert ExecutionMode.AI_VISION.value == "ai_vision"
        assert ExecutionMode.API.value == "api"
        assert ExecutionMode.UNKNOWN.value == "unknown"


class TestExecutionStrategyEnum:
    """ExecutionStrategy 枚举测试�?""
    
    def test_execution_strategy_values(self):
        """测试 ExecutionStrategy 枚举�?""
        assert ExecutionStrategy.STRICT.value == "strict"
        assert ExecutionStrategy.SMART.value == "smart"
        assert ExecutionStrategy.FAST.value == "fast"


class TestDefaultConfig:
    """默认配置测试�?""
    
    def test_default_config(self):
        """测试默认配置"""
        default = ExecutionModeSelector.DEFAULT_CONFIG
        
        assert default.mode == ExecutionMode.AI_VISION
        assert default.strategy == ExecutionStrategy.SMART
        assert default.headless is True
        assert default.record_video is False
    
    def test_case_type_mapping(self):
        """测试用例类型映射"""
        mapping = ExecutionModeSelector.CASE_TYPE_MAPPING
        
        assert mapping["UI"] == ExecutionMode.AI_VISION
        assert mapping["ui"] == ExecutionMode.AI_VISION
        assert mapping["功能"] == ExecutionMode.AI_VISION
        assert mapping["功能测试"] == ExecutionMode.AI_VISION
        assert mapping["API"] == ExecutionMode.API
        assert mapping["api"] == ExecutionMode.API
        assert mapping["接口"] == ExecutionMode.API
        assert mapping["接口测试"] == ExecutionMode.API
    
    def test_strategy_configs(self):
        """测试策略配置字典"""
        configs = ExecutionModeSelector.STRATEGY_CONFIGS
        
        assert ExecutionStrategy.STRICT in configs
        assert ExecutionStrategy.SMART in configs
        assert ExecutionStrategy.FAST in configs
        
        # 验证每个配置都是StrategyConfig类型
        for strategy, config in configs.items():
            assert isinstance(config, StrategyConfig)
