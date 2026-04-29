"""移动端AI动作Mixin - 实现移动端点击/输入/滑动等操作。
"""
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from app.utils.adb_controller import AdbController, AdbError, DeviceNotConnectedError
from app.utils.uiautomator_helper import UIAutomatorHelper, UIAutomatorError, UIElement
from app.utils.unified_vision_model import UnifiedVisionModel
from app.models.element_locator import ElementLocator
from app.services.mobile_ai_executor_types import (
    MobileActionType, MobileAIError, MobileDeviceError,
    MobileRecognitionError, MobileActionResult
)


class MobileAIActionsMixin:
    async def _execute_click(self, element_info: Dict[str, Any], step_desc: str) -> MobileActionResult:
        locator = await self._find_element(element_info)
        if not locator:
            return MobileActionResult(
                success=False, action_type=MobileActionType.CLICK,
                description=step_desc, error_message="元素未找到"
            )
        try:
            if locator.get('coordinates'):
                x, y = locator['coordinates']['x'], locator['coordinates']['y']
                self.adb_controller.tap(x, y)
            elif locator.get('resource_id'):
                self.uiautomator_helper.click(resource_id=locator['resource_id'])
            elif locator.get('text'):
                self.uiautomator_helper.click(text=locator['text'])
            elif locator.get('xpath'):
                self.uiautomator_helper.click(xpath=locator['xpath'])
            else:
                return MobileActionResult(
                    success=False, action_type=MobileActionType.CLICK,
                    description=step_desc, error_message="无有效定位方式"
                )
            await asyncio.sleep(self.action_delay)
            return MobileActionResult(
                success=True, action_type=MobileActionType.CLICK,
                description=step_desc, coordinates=locator.get('coordinates'),
                locator_info=locator
            )
        except (AdbError, UIAutomatorError) as e:
            return MobileActionResult(
                success=False, action_type=MobileActionType.CLICK,
                description=step_desc, error_message=str(e)
            )

    async def _execute_input(self, element_info: Dict[str, Any], input_text: str, step_desc: str) -> MobileActionResult:
        locator = await self._find_element(element_info)
        if not locator:
            return MobileActionResult(
                success=False, action_type=MobileActionType.INPUT,
                description=step_desc, error_message="输入框未找到"
            )
        try:
            if locator.get('resource_id'):
                self.uiautomator_helper.set_text(resource_id=locator['resource_id'], text=input_text)
            elif locator.get('text'):
                self.uiautomator_helper.click(text=locator['text'])
                await asyncio.sleep(0.3)
                self.adb_controller.input_text(input_text)
            elif locator.get('coordinates'):
                x, y = locator['coordinates']['x'], locator['coordinates']['y']
                self.adb_controller.tap(x, y)
                await asyncio.sleep(0.3)
                self.adb_controller.input_text(input_text)
            else:
                return MobileActionResult(
                    success=False, action_type=MobileActionType.INPUT,
                    description=step_desc, error_message="无有效定位方式"
                )
            await asyncio.sleep(self.action_delay)
            return MobileActionResult(
                success=True, action_type=MobileActionType.INPUT,
                description=step_desc, locator_info=locator
            )
        except (AdbError, UIAutomatorError) as e:
            return MobileActionResult(
                success=False, action_type=MobileActionType.INPUT,
                description=step_desc, error_message=str(e)
            )

    async def _execute_swipe(self, direction: str, distance: int = 500, step_desc: str = "") -> MobileActionResult:
        try:
            screen_size = self.adb_controller.get_screen_size()
            center_x = screen_size['width'] // 2
            center_y = screen_size['height'] // 2
            directions = {
                'up': (center_x, center_y + distance, center_x, center_y - distance),
                'down': (center_x, center_y - distance, center_x, center_y + distance),
                'left': (center_x + distance, center_y, center_x - distance, center_y),
                'right': (center_x - distance, center_y, center_x + distance, center_y),
            }
            if direction not in directions:
                return MobileActionResult(
                    success=False, action_type=MobileActionType.SWIPE,
                    description=step_desc, error_message=f"无效方向: {direction}"
                )
            x1, y1, x2, y2 = directions[direction]
            self.adb_controller.swipe(x1, y1, x2, y2, duration=300)
            await asyncio.sleep(self.action_delay)
            return MobileActionResult(
                success=True, action_type=MobileActionType.SWIPE,
                description=step_desc
            )
        except AdbError as e:
            return MobileActionResult(
                success=False, action_type=MobileActionType.SWIPE,
                description=step_desc, error_message=str(e)
            )

    async def _execute_press_key(self, key: str, step_desc: str) -> MobileActionResult:
        try:
            key_map = {
                'enter': 'KEYCODE_ENTER', 'back': 'KEYCODE_BACK',
                'home': 'KEYCODE_HOME', 'menu': 'KEYCODE_MENU',
                'search': 'KEYCODE_SEARCH', 'delete': 'KEYCODE_DEL',
            }
            keycode = key_map.get(key.lower(), key)
            self.adb_controller.press_key(keycode)
            await asyncio.sleep(self.action_delay)
            return MobileActionResult(
                success=True, action_type=MobileActionType.PRESS_KEY,
                description=step_desc
            )
        except AdbError as e:
            return MobileActionResult(
                success=False, action_type=MobileActionType.PRESS_KEY,
                description=step_desc, error_message=str(e)
            )

    async def _execute_verify(self, element_info: Dict[str, Any], step_desc: str) -> MobileActionResult:
        locator = await self._find_element(element_info)
        if locator:
            return MobileActionResult(
                success=True, action_type=MobileActionType.VERIFY,
                description=step_desc, locator_info=locator
            )
        return MobileActionResult(
            success=False, action_type=MobileActionType.VERIFY,
            description=step_desc, error_message="验证元素未找到"
        )
