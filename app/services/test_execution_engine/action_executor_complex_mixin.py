"""复杂动作执行Mixin - 处理拖拽、键盘操作和自定义动作。
"""
from app.services.test_execution_engine.action_executor_input_click_mixin import ActionExecutorInputClickMixin
from app.services.test_execution_engine.structured_assertion_mixin import StructuredAssertionMixin
from app.services.test_execution_engine.action_executor_hover_select_mixin import ActionExecutorHoverSelectMixin


class ActionExecutorComplexMixin(
    ActionExecutorInputClickMixin,
    StructuredAssertionMixin,
    ActionExecutorHoverSelectMixin
):
    pass
