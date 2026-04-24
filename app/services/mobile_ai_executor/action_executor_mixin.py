"""移动端AI动作执行Mixin - 各类移动端操作的执行逻辑。"""
import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from app.utils.adb_controller import AdbController, AdbError
from app.utils.uiautomator_helper import UIAutomatorHelper, UIAutomatorError
from app.services.mobile_ai_executor.types import (
    MobileActionType, MobileActionResult, MobileAIError, MobileDeviceError,
)


class MobileActionExecutorMixin:
    """动作执行：点击、输入、滑动、按键、启动应用、验证等。"""

    async def execute_action(
        self,
        description: str,
        step_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> MobileActionResult:
        logger.info(f"MobileAIExecutor: 执行操作 '{description}'")
        action_type = self.parse_action(description)
        try:
            if not await self.adb.is_device_connected():
                raise MobileDeviceError("设备未连接")
            if action_type == MobileActionType.CLICK:
                return await self._execute_click(description, step_id, use_cache)
            elif action_type == MobileActionType.INPUT:
                return await self._execute_input(description, step_id, use_cache)
            elif action_type in (
                MobileActionType.SCROLL_UP, MobileActionType.SCROLL_DOWN,
                MobileActionType.SCROLL_LEFT, MobileActionType.SCROLL_RIGHT
            ):
                return await self._execute_scroll(action_type)
            elif action_type == MobileActionType.SWIPE:
                return await self._execute_swipe(description)
            elif action_type == MobileActionType.PRESS_KEY:
                return await self._execute_press_key(description)
            elif action_type == MobileActionType.GO_BACK:
                await self.adb.press_back()
                return MobileActionResult(success=True, action_type=action_type, description=description)
            elif action_type == MobileActionType.GO_HOME:
                await self.adb.press_home()
                return MobileActionResult(success=True, action_type=action_type, description=description)
            elif action_type == MobileActionType.LAUNCH_APP:
                return await self._execute_launch_app(description)
            elif action_type == MobileActionType.WAIT:
                await asyncio.sleep(2)
                return MobileActionResult(success=True, action_type=action_type, description=description)
            elif action_type == MobileActionType.VERIFY:
                return await self._execute_verify(description)
            else:
                return MobileActionResult(
                    success=False, action_type=action_type, description=description,
                    error_message=f"不支持的操作类型: {action_type}"
                )
        except MobileAIError:
            raise
        except AdbError as e:
            raise MobileDeviceError(f"ADB操作失败: {e}")
        except Exception as e:
            raise MobileAIError(f"执行失败: {e}")

    async def _execute_click(
        self, description: str, step_id: Optional[int] = None, use_cache: bool = True
    ) -> MobileActionResult:
        if use_cache and step_id:
            cached = self._get_cached_locator(step_id)
            if cached:
                result = await self._try_cached_click(cached, description)
                if result:
                    result.used_cache = True
                    return result
                logger.info("缓存定位失效，降级到AI实时识别")
        element_info = await self._recognize_element(description)
        if not element_info:
            raise MobileRecognitionError(f"AI无法识别目标元素: {description}")
        x = element_info.get("x", 0)
        y = element_info.get("y", 0)
        confidence = element_info.get("confidence", 0)
        await self.adb.click(x, y)
        locator_info = None
        if step_id and confidence >= self.CACHE_CONFIDENCE_THRESHOLD:
            locator_info = await self._cache_locator(step_id, description, element_info)
        return MobileActionResult(
            success=True, action_type=MobileActionType.CLICK, description=description,
            coordinates={"x": x, "y": y}, locator_info=locator_info, ai_confidence=confidence,
        )

    async def _execute_input(
        self, description: str, step_id: Optional[int] = None, use_cache: bool = True
    ) -> MobileActionResult:
        input_text = self._extract_input_text(description)
        target_desc = self._extract_input_target(description)
        if target_desc:
            click_result = await self._execute_click(target_desc, step_id, use_cache)
            if not click_result.success:
                return MobileActionResult(
                    success=False, action_type=MobileActionType.INPUT, description=description,
                    error_message=f"无法定位输入框: {target_desc}",
                )
            await asyncio.sleep(0.5)
        if input_text:
            await self.adb.input_text(input_text)
        else:
            logger.warning(f"输入操作未提取到文本内容: {description}")
        return MobileActionResult(success=True, action_type=MobileActionType.INPUT, description=description)

    async def _execute_scroll(self, action_type: MobileActionType) -> MobileActionResult:
        screen_size = await self.adb.get_screen_size()
        width, height = screen_size
        center_x = width // 2
        if action_type == MobileActionType.SCROLL_UP:
            await self.adb.swipe(center_x, height * 3 // 4, center_x, height // 4, 500)
        elif action_type == MobileActionType.SCROLL_DOWN:
            await self.adb.swipe(center_x, height // 4, center_x, height * 3 // 4, 500)
        elif action_type == MobileActionType.SCROLL_LEFT:
            await self.adb.swipe(width * 3 // 4, height // 2, width // 4, height // 2, 500)
        elif action_type == MobileActionType.SCROLL_RIGHT:
            await self.adb.swipe(width // 4, height // 2, width * 3 // 4, height // 2, 500)
        return MobileActionResult(success=True, action_type=action_type, description=action_type.value)

    async def _execute_swipe(self, description: str) -> MobileActionResult:
        screen_size = await self.adb.get_screen_size()
        width, height = screen_size
        await self.adb.swipe(width // 2, height * 2 // 3, width // 2, height // 3, 500)
        return MobileActionResult(success=True, action_type=MobileActionType.SWIPE, description=description)

    async def _execute_press_key(self, description: str) -> MobileActionResult:
        desc = description.lower()
        key_map = {
            "enter": 66, "回车": 66,
            "back": 4, "返回": 4,
            "home": 3, "主页": 3,
            "delete": 67, "删除": 67,
            "tab": 61,
        }
        for key_name, keycode in key_map.items():
            if key_name in desc:
                await self.adb.press_key(keycode)
                return MobileActionResult(success=True, action_type=MobileActionType.PRESS_KEY, description=description)
        logger.warning(f"未识别的按键描述: {description}，默认按回车键")
        await self.adb.press_key(66)
        return MobileActionResult(success=True, action_type=MobileActionType.PRESS_KEY, description=description)

    async def _execute_launch_app(self, description: str) -> MobileActionResult:
        package_activity = self._extract_package_activity(description)
        if package_activity:
            package, activity = package_activity
            await self.adb.start_app(package, activity)
            return MobileActionResult(success=True, action_type=MobileActionType.LAUNCH_APP, description=description)
        raise MobileAIError(f"无法解析应用包名和Activity: {description}")

    async def _execute_verify(self, description: str) -> MobileActionResult:
        screenshot = await self.adb.take_screenshot()
        verify_prompt = (
            f"请验证当前页面是否符合以下预期：{description}\n"
            "请以JSON格式返回结果，包含passed字段(boolean)和reason字段(string)。"
        )
        verify_response = self.vision_model.analyze_image(
            screenshot, prompt=verify_prompt,
            system_prompt="你是一个专业的UI测试工程师，擅长验证页面状态是否符合预期。",
        )
        is_passed = False
        if verify_response:
            try:
                json_match = re.search(r'\{[^}]+\}', verify_response)
                if json_match:
                    result_data = json.loads(json_match.group())
                    is_passed = bool(result_data.get("passed", False))
            except (json.JSONDecodeError, ValueError):
                is_passed = "通过" in verify_response or "true" in verify_response.lower()
        return MobileActionResult(success=is_passed, action_type=MobileActionType.VERIFY, description=description)
