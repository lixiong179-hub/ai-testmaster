"""自愈基础Mixin - 提供元素定位失败时的自愈修复基础能力。

本Mixin是自愈体系的组合入口，通过多继承组合执行和策略两个Mixin。
提供统一的初始化和统计接口。

Mixin组合（MRO顺序）:
    - SelfHealingExecuteMixin: 自愈执行（执行时的自愈逻辑）
    - SelfHealingStrategyMixin: 自愈策略（具体自愈方法实现）

自愈流程:
    1. 步骤执行失败
    2. 调用 _execute_with_self_healing
    3. 尝试多种自愈策略（AI Vision / Local AI / Stagehand）
    4. 策略成功则更新定位器并重试
    5. 记录自愈统计

使用方式:
    class TestEngine(SelfHealingMixin, ...):
        pass
"""
from typing import Dict, Any

from app.services.test_execution_engine.self_healing_execute_mixin import SelfHealingExecuteMixin
from app.services.test_execution_engine.self_healing_strategy_mixin import SelfHealingStrategyMixin


class SelfHealingMixin(SelfHealingExecuteMixin, SelfHealingStrategyMixin):
    """自愈基础Mixin - 组合自愈执行和策略，提供统一的自愈能力。

    继承顺序（MRO）:
        SelfHealingExecuteMixin -> SelfHealingStrategyMixin

        SelfHealingExecuteMixin在底层，提供执行时的自愈入口。
        SelfHealingStrategyMixin在上层，提供具体的自愈策略实现。

    初始化属性:
        _self_healing_stats: 自愈统计信息
        _stagehand_instance: Stagehand服务实例缓存

    使用场景:
        - 测试执行过程中元素定位失败时的自动修复
        - 通过AI视觉/本地AI/Stagehand等多种策略恢复执行
        - 自愈统计和历史记录
    """

    def __init__(self) -> None:
        """初始化自愈Mixin。

        初始化自愈统计信息，用于记录自愈尝试次数、成功次数等信息。
        注意：由于Mixin可能被多次实例化，此初始化是幂等的。
        """
        if not hasattr(self, '_self_healing_stats') or self._self_healing_stats is None:
            self._self_healing_stats: Dict[str, Any] = {
                "total_attempts": 0,      # 总尝试次数
                "total_healed": 0,         # 成功修复次数
                "failed_attempts": 0,      # 失败次数
                "healed_steps": [],        # 修复成功的步骤记录
                "strategy_usage": {},      # 各策略使用次数
            }

        if not hasattr(self, '_stagehand_instance'):
            self._stagehand_instance = None

        if not hasattr(self, '_self_healing_attempts'):
            self._self_healing_attempts = 0

        if not hasattr(self, '_self_healing_successes'):
            self._self_healing_successes = 0
