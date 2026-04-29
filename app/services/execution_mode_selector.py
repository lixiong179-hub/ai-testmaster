"""执行模式选择器 - 根据用例类型选择执行模式和策略配置。

本模块实现执行模式和策略的选择逻辑，将用例类型映射到对应的
执行模式（AI视觉/API/未知），并提供三种预设策略配置
（严格/智能/快速）。

核心类:
    - ExecutionModeSelector: 执行模式选择器

核心函数:
    - get_execution_mode_selector: 工厂函数，获取选择器实例

执行模式:
    - AI_VISION: AI视觉模式，用于UI自动化测试
    - API: API模式，用于接口自动化测试
    - UNKNOWN: 未知模式，用于性能/安全等特殊测试

执行策略:
    - STRICT(严格): 高置信度阈值(0.95)、3次重试、不批量识别
    - SMART(智能): 中置信度阈值(0.9)、1次重试、批量识别5个
    - FAST(快速): 低置信度阈值(0.85)、无重试、批量识别10个

配置优先级:
    全局配置 < 任务配置 < 用例配置
    后者覆盖前者，实现精细化控制。

依赖关系:
    - app.services.execution_mode_types: 执行模式类型定义
"""
from typing import Optional
from loguru import logger
from app.services.execution_mode_types import (
    ExecutionMode, ExecutionStrategy, StrategyConfig, ExecutionConfig
)


class ExecutionModeSelector:
    """执行模式选择器 - 根据用例类型选择执行模式和策略。

    职责:
        - 用例类型到执行模式的映射
        - 执行策略的选择
        - 策略配置的获取
        - 完整执行配置的组装（含优先级覆盖）

    用例类型映射:
        UI相关(ui_automation/UI/功能/functional/manual) -> AI_VISION
        API相关(api_automation/API/接口/api_auto) -> API
        其他(performance/security) -> UNKNOWN

    使用场景:
        - 任务执行前根据用例类型选择执行引擎
        - 根据场景选择执行策略（调试用STRICT，CI用FAST）
        - 组装完整的ExecutionConfig供执行引擎使用
    """

    # 默认执行配置
    DEFAULT_CONFIG = ExecutionConfig(
        mode=ExecutionMode.AI_VISION,
        strategy=ExecutionStrategy.SMART,
        headless=True,
        record_video=False
    )

    # 用例类型到执行模式的映射表
    CASE_TYPE_MAPPING = {
        "ui_automation": ExecutionMode.AI_VISION,
        "UI": ExecutionMode.AI_VISION,
        "ui": ExecutionMode.AI_VISION,
        "功能": ExecutionMode.AI_VISION,
        "功能测试": ExecutionMode.AI_VISION,
        "functional": ExecutionMode.AI_VISION,
        "manual": ExecutionMode.AI_VISION,
        "api_automation": ExecutionMode.API,
        "API": ExecutionMode.API,
        "api": ExecutionMode.API,
        "接口": ExecutionMode.API,
        "接口测试": ExecutionMode.API,
        "api_auto": ExecutionMode.API,
        "performance": ExecutionMode.UNKNOWN,
        "security": ExecutionMode.UNKNOWN,
    }

    # 执行策略到策略配置的映射表
    STRATEGY_CONFIGS = {
        ExecutionStrategy.STRICT: StrategyConfig(
            use_css_selector=True, use_xpath=True, use_ai_vision=True,
            max_retries=3, retry_delay=2.0, ai_timeout=45,
            confidence_threshold=0.95, use_locator_cache=True,
            cache_ttl_minutes=120, enable_batch_recognition=False, batch_size=1
        ),
        ExecutionStrategy.SMART: StrategyConfig(
            use_css_selector=True, use_xpath=True, use_ai_vision=True,
            max_retries=1, retry_delay=1.0, ai_timeout=30,
            confidence_threshold=0.9, use_locator_cache=True,
            cache_ttl_minutes=60, enable_batch_recognition=True, batch_size=5
        ),
        ExecutionStrategy.FAST: StrategyConfig(
            use_css_selector=True, use_xpath=False, use_ai_vision=True,
            max_retries=0, retry_delay=0.0, ai_timeout=20,
            confidence_threshold=0.85, use_locator_cache=False,
            cache_ttl_minutes=30, enable_batch_recognition=True, batch_size=10
        )
    }

    @classmethod
    def select_mode(cls, case_type: str) -> ExecutionMode:
        """根据用例类型选择执行模式。

        Args:
            case_type: 用例类型字符串。

        Returns:
            ExecutionMode枚举值，未知类型默认返回AI_VISION。
        """
        if not case_type:
            logger.warning("用例类型为空，使用默认AI视觉模式")
            return ExecutionMode.AI_VISION
        mode = cls.CASE_TYPE_MAPPING.get(case_type.strip())
        if not mode:
            logger.warning(f"未知的用例类型: {case_type}，使用默认AI视觉模式")
            return ExecutionMode.AI_VISION
        logger.info(f"用例类型 '{case_type}' 映射到执行模式: {mode.value}")
        return mode

    @classmethod
    def select_strategy(cls, strategy_name: Optional[str] = None) -> ExecutionStrategy:
        """根据策略名称选择执行策略。

        Args:
            strategy_name: 策略名称（strict/smart/fast），可选。

        Returns:
            ExecutionStrategy枚举值，默认返回SMART。
        """
        if not strategy_name:
            return ExecutionStrategy.SMART
        strategy_map = {
            "strict": ExecutionStrategy.STRICT,
            "smart": ExecutionStrategy.SMART,
            "fast": ExecutionStrategy.FAST,
        }
        strategy = strategy_map.get(strategy_name.lower())
        if not strategy:
            logger.warning(f"未知的执行策略: {strategy_name}，使用默认SMART模式")
            return ExecutionStrategy.SMART
        return strategy

    @classmethod
    def get_strategy_config(cls, strategy: ExecutionStrategy) -> StrategyConfig:
        """获取执行策略对应的详细配置。

        Args:
            strategy: ExecutionStrategy枚举值。

        Returns:
            StrategyConfig实例，未知策略返回SMART配置。
        """
        return cls.STRATEGY_CONFIGS.get(strategy, cls.STRATEGY_CONFIGS[ExecutionStrategy.SMART])

    @classmethod
    def get_execution_config(
        cls,
        case_type: str,
        global_headless: Optional[bool] = None,
        global_record_video: Optional[bool] = None,
        global_strategy: Optional[str] = None,
        task_headless: Optional[bool] = None,
        task_record_video: Optional[bool] = None,
        task_strategy: Optional[str] = None,
        case_headless: Optional[bool] = None,
        case_record_video: Optional[bool] = None,
        case_strategy: Optional[str] = None,
        video_path: Optional[str] = None
    ) -> ExecutionConfig:
        """组装完整的执行配置，支持全局/任务/用例三层覆盖。

        覆盖优先级（后者覆盖前者）:
            默认值 < 全局配置 < 任务配置 < 用例配置

        Args:
            case_type: 用例类型，用于选择执行模式。
            global_headless/global_record_video/global_strategy: 全局配置。
            task_headless/task_record_video/task_strategy: 任务配置。
            case_headless/case_record_video/case_strategy: 用例配置。
            video_path: 视频输出路径，可选。

        Returns:
            完整的ExecutionConfig实例。
        """
        # 选择执行模式
        mode = cls.select_mode(case_type)

        # 策略覆盖：全局 -> 任务 -> 用例
        strategy = cls.DEFAULT_CONFIG.strategy
        if global_strategy:
            strategy = cls.select_strategy(global_strategy)
        if task_strategy:
            strategy = cls.select_strategy(task_strategy)
        if case_strategy:
            strategy = cls.select_strategy(case_strategy)

        # headless覆盖：全局 -> 任务 -> 用例
        headless = cls.DEFAULT_CONFIG.headless
        if global_headless is not None:
            headless = global_headless
        if task_headless is not None:
            headless = task_headless
        if case_headless is not None:
            headless = case_headless

        # record_video覆盖：全局 -> 任务 -> 用例
        record_video = cls.DEFAULT_CONFIG.record_video
        if global_record_video is not None:
            record_video = global_record_video
        if task_record_video is not None:
            record_video = task_record_video
        if case_record_video is not None:
            record_video = case_record_video

        # 获取策略详细配置
        strategy_config = cls.get_strategy_config(strategy)

        config = ExecutionConfig(
            mode=mode,
            strategy=strategy,
            headless=headless,
            record_video=record_video,
            video_path=video_path,
            strategy_config=strategy_config
        )
        logger.info(
            f"执行配置: mode={config.mode.value}, "
            f"strategy={config.strategy.value}, "
            f"headless={config.headless}, "
            f"record_video={config.record_video}"
        )
        return config

    @classmethod
    def is_ai_vision_case(cls, case_type: str) -> bool:
        """判断用例类型是否为AI视觉模式。

        Args:
            case_type: 用例类型字符串。

        Returns:
            是AI视觉模式返回True。
        """
        mode = cls.select_mode(case_type)
        return mode == ExecutionMode.AI_VISION

    @classmethod
    def is_api_case(cls, case_type: str) -> bool:
        """判断用例类型是否为API模式。

        Args:
            case_type: 用例类型字符串。

        Returns:
            是API模式返回True。
        """
        mode = cls.select_mode(case_type)
        return mode == ExecutionMode.API


def get_execution_mode_selector() -> ExecutionModeSelector:
    """工厂函数 - 获取ExecutionModeSelector实例。

    Returns:
        ExecutionModeSelector实例。
    """
    return ExecutionModeSelector()
