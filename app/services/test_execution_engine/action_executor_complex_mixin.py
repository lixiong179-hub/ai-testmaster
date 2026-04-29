"""复杂动作执行Mixin - 处理拖拽、键盘操作和自定义动作。
"""
from app.services.test_execution_engine.action_executor_input_click_mixin import ActionExecutorInputClickMixin
from app.services.test_execution_engine.action_executor_verify_captcha_mixin import ActionExecutorVerifyCaptchaMixin
from app.services.test_execution_engine.action_executor_hover_select_mixin import ActionExecutorHoverSelectMixin


class ActionExecutorComplexMixin(
    ActionExecutorInputClickMixin,
    ActionExecutorVerifyCaptchaMixin,
    ActionExecutorHoverSelectMixin
):
    pass
