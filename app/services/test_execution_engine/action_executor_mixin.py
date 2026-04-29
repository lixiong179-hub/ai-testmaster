"""动作执行分发Mixin - 根据ActionType分发到具体的动作执行器。

本Mixin是动作执行体系的统一入口，通过多继承组合基础动作和复杂动作两个Mixin。
提供 execute_action 统一入口方法，根据 action_type 分发到具体的执行逻辑。

Mixin组合（MRO顺序）:
    - ActionExecutorBasicMixin: 基础动作（导航、等待、刷新、按键）
    - ActionExecutorComplexMixin: 复杂动作（点击、输入、悬停、选择、验证码）

执行流程:
    execute_action(step, action_info)
    -> _parse_step_action() 解析动作类型
    -> _execute_action_by_type() 分发到具体动作
    -> ActionType 对应的具体Mixin方法

使用方式:
    class TestEngine(ActionExecutorMixin, ...):
        pass

    # 调用入口
    await engine.execute_action(step, action_info, step_id, test_data)
"""
from typing import Optional, Dict, Any

from app.services.test_execution_engine.action_executor_basic_mixin import ActionExecutorBasicMixin
from app.services.test_execution_engine.action_executor_complex_mixin import ActionExecutorComplexMixin
from app.services.test_execution_engine.models import ActionType, StepExecutionError


class ActionExecutorMixin(ActionExecutorBasicMixin, ActionExecutorComplexMixin):
    """动作执行分发Mixin - 统一的动作执行入口。

    继承顺序（MRO）:
        ActionExecutorBasicMixin -> ActionExecutorComplexMixin

        ActionExecutorBasicMixin在底层，提供基础动作执行（导航、等待、刷新、按键）。
        ActionExecutorComplexMixin在上层，组合了点击/输入/悬停/选择/验证码等复杂动作。

    核心方法:
        execute_action: 统一入口，根据 action_type 分发到具体执行逻辑

    使用场景:
        - 测试步骤执行
        - 前置条件动作执行
        - 移动端动作执行
    """

    async def execute_action(
        self,
        step: Any,
        action_info: Dict[str, Any],
        step_id: Optional[int] = None,
        step_test_data: Optional[Dict[str, str]] = None
    ) -> None:
        """统一动作执行入口 - 根据动作类型分发到具体的执行方法。

        执行流程:
            1. 从 action_info 提取动作类型
            2. 调用 _execute_action_by_type 分发到具体动作
            3. 具体动作包括：导航、点击、输入、悬停、选择、验证码、等待、滚动等

        Args:
            step: 测试步骤对象（包含 step_number 等信息）
            action_info: 动作信息字典，包含:
                - type: ActionType 动作类型
                - text: 动作描述文本
                - input_value: 输入值（可选）
            step_id: 步骤ID（可选）
            step_test_data: 测试数据参数字典（可选）

        Raises:
            StepExecutionError: 动作执行失败时抛出

        示例:
            action_info = {"type": ActionType.CLICK, "text": "点击登录按钮"}
            await self.execute_action(step, action_info, step_id=1)
        """
        action_type = action_info.get("type", ActionType.CLICK)

        if step_id is None:
            step_id = getattr(step, 'id', None)

        await self._execute_action_by_type(
            action_type,
            action_info,
            step_id,
            step_test_data
        )

    def _parse_step_action(self, action_text: str) -> Dict[str, Any]:
        """解析步骤动作文本为结构化信息。

        该方法继承自 ActionExecutorBasicMixin，提供动作类型的自动识别。
        支持识别：导航、验证码、刷新、按键、输入、点击、验证、等待、滚动、悬停、选择等动作。

        Args:
            action_text: 动作描述文本

        Returns:
            包含 type (ActionType) 和 text (原始文本) 的字典
        """
        return ActionExecutorBasicMixin._parse_step_action(self, action_text)
