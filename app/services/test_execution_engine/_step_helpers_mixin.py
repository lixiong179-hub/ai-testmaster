"""步骤执行 - 辅助方法子 Mixin。

从 step_executor_mixin.py 拆分，承载步骤执行的辅助方法：
- _prepare_step_data: 准备步骤测试数据和替换后的操作描述
- _resolve_action_type: 解析步骤的动作类型
- _resolve_locator: 解析步骤的元素定位器
- _dispatch_step_action: 分发步骤动作到对应的执行方法
- _finalize_step_result: 完成步骤结果的时间记录
"""
from typing import Any, Dict

from loguru import logger

from app.models.test_case import TestStep
from app.services.test_execution_engine.models import ActionType, StepExecutionResult


class StepHelpersMixin:
    """步骤执行辅助方法子 Mixin。

    依赖聚合类提供：
    - self.enable_test_data_param / self.parameterizer（来自 TestDataMixin）
    - self._generate_step_test_data / self._substitute_parameters_in_action（来自 TestDataMixin）
    - self._parse_step_action（来自 ActionExecutorMixin）
    - self.locator_service / self.browser（来自 TestExecutionEngineV2）
    - self._get_current_page_title / self._save_realtime_locator（来自其他 Mixin）
    - 各 self._execute_* 动作执行方法（来自 ActionExecutor*Mixin）
    """

    def _prepare_step_data(self, step: TestStep) -> tuple:
        """准备步骤测试数据和替换后的操作描述。"""
        step_test_data = {}
        action_with_data = step.action

        if self.enable_test_data_param:
            step_test_data = self._generate_step_test_data(step.id, self.parameterizer)
            if step_test_data:
                logger.info(f"步骤 {step.step_number}: 生成的测试数据: {step_test_data}")
                action_with_data = self._substitute_parameters_in_action(step.action, step_test_data)
                if action_with_data != step.action:
                    logger.info(f"步骤 {step.step_number}: 替换后操作: {action_with_data}")

        return step_test_data, action_with_data

    def _resolve_action_type(self, step: TestStep, action_with_data: str) -> tuple:
        """解析步骤的动作类型。"""
        if hasattr(step, 'action_type') and step.action_type:
            action_type_str = step.action_type.lower()
            action_type_map = {
                "click": ActionType.CLICK, "input": ActionType.INPUT,
                "navigate": ActionType.NAVIGATE, "verify": ActionType.VERIFY,
                "wait": ActionType.WAIT, "scroll": ActionType.SCROLL,
                "hover": ActionType.HOVER, "select": ActionType.SELECT,
                "captcha": ActionType.VERIFY_CAPTCHA, "verify_captcha": ActionType.VERIFY_CAPTCHA,
                "refresh": ActionType.REFRESH,
                "keypress": ActionType.KEYBOARD, "keyboard": ActionType.KEYBOARD,
                "screenshot": ActionType.SCREENSHOT,
                "upload": ActionType.UPLOAD,
                "switch_frame": ActionType.SWITCH_FRAME,
                "switch_window": ActionType.SWITCH_WINDOW,
                "execute_script": ActionType.EXECUTE_SCRIPT,
            }
            action_type = action_type_map.get(action_type_str, ActionType.CLICK)
            action_info = {"type": action_type, "text": action_with_data}
        else:
            action_info = self._parse_step_action(action_with_data)
            action_type = action_info.get("type", ActionType.CLICK)
        return action_type, action_info

    async def _resolve_locator(
        self, step: TestStep, action_type: ActionType,
        action_with_data: str, execution_mode: str
    ) -> tuple:
        """解析步骤的元素定位器。"""
        locator_record = None
        element_info = None
        direct_executed = False

        if self.locator_service and step.id:
            locator_record = self.locator_service.get_locator(step.id)

        if execution_mode in ("realtime", "smart"):
            if not locator_record and self.locator_service and self.browser:
                logger.info(f"步骤 {step.step_number}: 无预存定位，尝试AI实时识别 (mode={execution_mode})")
                try:
                    page_title = await self._get_current_page_title()
                    element_info = await self.locator_service.smart_locate_element(
                        action_description=action_with_data,
                        page_title=page_title,
                        action_type=action_type.value if isinstance(action_type, ActionType) else action_type,
                        input_value=None
                    )
                    if element_info:
                        direct_executed = element_info.pop("_direct_executed", False)
                        locator_record = await self._save_realtime_locator(step, element_info)
                        if locator_record and not direct_executed:
                            logger.info(f"步骤 {step.step_number}: AI实时识别成功，已缓存定位信息")
                    else:
                        if execution_mode == "realtime":
                            logger.warning(f"步骤 {step.step_number}: AI实时识别失败")
                except Exception as e:
                    logger.warning(f"步骤 {step.step_number}: AI实时识别异常: {e}")

        return locator_record, element_info, direct_executed

    async def _dispatch_step_action(
        self, step, action_type: ActionType, action_info: Dict[str, Any],
        step_test_data: Dict[str, str], locator_record, element_info, direct_executed: bool
    ) -> None:
        """分发步骤动作到对应的执行方法。"""
        if action_type == ActionType.NAVIGATE:
            await self._execute_navigate(action_info)
        elif action_type in (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT):
            if element_info and direct_executed:
                pass
            elif locator_record:
                await self._execute_with_self_healing(step, locator_record, action_type, action_info, step_test_data)
            else:
                await self._execute_action_by_type(action_type, action_info, step, step_test_data)
        elif action_type == ActionType.VERIFY:
            await self._execute_verify(action_info, step.id)
        elif action_type == ActionType.WAIT:
            await self._execute_wait(action_info)
        elif action_type == ActionType.SCROLL:
            await self._execute_scroll(action_info)
        elif action_type == ActionType.SWITCH_FRAME:
            await self._execute_switch_frame(action_info, step)
        elif action_type == ActionType.SWITCH_WINDOW:
            await self._execute_switch_window(action_info, step)
        elif action_type == ActionType.UPLOAD:
            await self._execute_upload(action_info, step)
        elif action_type == ActionType.EXECUTE_SCRIPT:
            await self._execute_execute_script(action_info, step)
        elif action_type == ActionType.SCREENSHOT:
            await self._execute_screenshot(action_info)
        elif action_type in (ActionType.CAPTCHA, ActionType.VERIFY_CAPTCHA):
            await self._execute_captcha(action_info, step.id)
        elif action_type == ActionType.REFRESH:
            await self._execute_refresh(action_info)
        elif action_type in (ActionType.KEYPRESS, ActionType.KEYBOARD):
            await self._execute_keypress(action_info)
        else:
            await self._execute_click(action_info, step.id, step_test_data)

    def _finalize_step_result(self, result: StepExecutionResult, start_time) -> StepExecutionResult:
        """完成步骤结果的时间记录。"""
        from app.utils.db_time import utcnow
        end_time = utcnow()
        duration = int((end_time - start_time).total_seconds() * 1000)
        result.end_time = end_time
        result.duration_ms = duration
        return result


__all__ = ["StepHelpersMixin"]
