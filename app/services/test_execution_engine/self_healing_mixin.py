"""自愈基础Mixin - 提供元素定位失败时的自愈修复基础能力。

本Mixin是自愈体系的组合入口，通过多继承组合执行和策略两个Mixin。
提供统一的初始化和统计接口。

注意：当前 __init__.py 中直接引用 SelfHealingExecuteMixin 和
SelfHealingStrategyMixin，本模块保留作为兼容性入口。
"""
from app.services.test_execution_engine.self_healing_execute_mixin import SelfHealingExecuteMixin
from app.services.test_execution_engine.self_healing_strategy_mixin import SelfHealingStrategyMixin


class SelfHealingMixin(SelfHealingExecuteMixin, SelfHealingStrategyMixin):
    """自愈基础Mixin - 组合自愈执行和策略，提供统一的自愈能力。"""

    pass
