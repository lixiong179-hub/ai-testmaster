import re
import json
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from loguru import logger
from sqlalchemy.orm import Session

from app.utils.adb_controller import AdbController, AdbError, DeviceNotConnectedError
from app.utils.uiautomator_helper import UIAutomatorHelper, UIAutomatorError, UIElement
from app.utils.unified_vision_model import UnifiedVisionModel, create_vision_model
from app.models.element_locator import ElementLocator


class MobileActionType(str, Enum):
    CLICK = "click"
    INPUT = "input"
    SWIPE = "swipe"
    PRESS_KEY = "press_key"
    WAIT = "wait"
    VERIFY = "verify"
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    SCROLL_LEFT = "scroll_left"
    SCROLL_RIGHT = "scroll_right"
    LAUNCH_APP = "launch_app"
    GO_BACK = "go_back"
    GO_HOME = "go_home"


class MobileAIError(Exception):
    pass


class MobileDeviceError(MobileAIError):
    pass


class MobileRecognitionError(MobileAIError):
    pass


@dataclass
class MobileActionResult:
    success: bool
    action_type: MobileActionType
    description: str
    coordinates: Optional[Dict[str, int]] = None
    locator_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    ai_confidence: float = 0.0
    used_cache: bool = False
    cached_locator: Optional[Dict[str, Any]] = None


class MobileAIExecutor:
    MIN_CONFIDENCE_THRESHOLD = 0.7
    CACHE_CONFIDENCE_THRESHOLD = 0.8

    def __init__(
        self,
        db: Session,
        adb: AdbController,
        vision_model: Optional[UnifiedVisionModel] = None,
        uiautomator: Optional[UIAutomatorHelper] = None,
    ):
        self.db = db
        self.adb = adb
        self.vision_model = vision_model or create_vision_model()
        self.uiautomator = uiautomator or UIAutomatorHelper(adb)

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
            elif action_type in (MobileActionType.SCROLL_UP, MobileActionType.SCROLL_DOWN,
                                  MobileActionType.SCROLL_LEFT, MobileActionType.SCROLL_RIGHT):
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
                return MobileActionResult(success=False, action_type=action_type, description=description, error_message=f"不支持的操作类型: {action_type}")
        except MobileAIError:
            raise
        except AdbError as e:
            raise MobileDeviceError(f"ADB操作失败: {e}")
        except Exception as e:
            raise MobileAIError(f"执行失败: {e}")

    def parse_action(self, description: str) -> MobileActionType:
        desc = description.lower().strip()
        if any(kw in desc for kw in ["返回", "后退", "back"]):
            return MobileActionType.GO_BACK
        if any(kw in desc for kw in ["主页", "首页", "home", "桌面"]):
            if "导航" not in desc and "跳转" not in desc:
                return MobileActionType.GO_HOME
        if any(kw in desc for kw in ["向上滑动", "上滑", "scroll up", "向上滚动"]):
            return MobileActionType.SCROLL_UP
        if any(kw in desc for kw in ["向下滑动", "下滑", "scroll down", "向下滚动"]):
            return MobileActionType.SCROLL_DOWN
        if any(kw in desc for kw in ["向左滑动", "左滑", "scroll left"]):
            return MobileActionType.SCROLL_LEFT
        if any(kw in desc for kw in ["向右滑动", "右滑", "scroll right"]):
            return MobileActionType.SCROLL_RIGHT
        if any(kw in desc for kw in ["输入", "填写", "填入", "键入", "input", "type"]):
            return MobileActionType.INPUT
        if any(kw in desc for kw in ["滑动", "swipe"]):
            return MobileActionType.SWIPE
        if any(kw in desc for kw in ["按键", "按", "press"]):
            return MobileActionType.PRESS_KEY
        if any(kw in desc for kw in ["启动", "打开应用", "launch", "open app"]):
            return MobileActionType.LAUNCH_APP
        if any(kw in desc for kw in ["等待", "wait"]):
            return MobileActionType.WAIT
        if any(kw in desc for kw in ["验证", "检查", "确认", "verify", "check", "assert"]):
            return MobileActionType.VERIFY
        return MobileActionType.CLICK

    async def _execute_click(
        self,
        description: str,
        step_id: Optional[int] = None,
        use_cache: bool = True,
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
            success=True,
            action_type=MobileActionType.CLICK,
            description=description,
            coordinates={"x": x, "y": y},
            locator_info=locator_info,
            ai_confidence=confidence,
        )

    async def _execute_input(
        self,
        description: str,
        step_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> MobileActionResult:
        input_text = self._extract_input_text(description)
        target_desc = self._extract_input_target(description)
        if target_desc:
            click_result = await self._execute_click(target_desc, step_id, use_cache)
            if not click_result.success:
                return MobileActionResult(
                    success=False,
                    action_type=MobileActionType.INPUT,
                    description=description,
                    error_message=f"无法定位输入框: {target_desc}",
                )
            await asyncio.sleep(0.5)
        if input_text:
            await self.adb.input_text(input_text)
        else:
            logger.warning(f"输入操作未提取到文本内容: {description}")
        return MobileActionResult(
            success=True,
            action_type=MobileActionType.INPUT,
            description=description,
        )

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
            screenshot,
            prompt=verify_prompt,
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
        return MobileActionResult(
            success=is_passed,
            action_type=MobileActionType.VERIFY,
            description=description,
        )

    async def _recognize_element(self, description: str) -> Optional[Dict[str, Any]]:
        try:
            screenshot = await self.adb.take_screenshot()
            elements = self.vision_model.recognize_elements(screenshot, description)
            if not elements:
                return None
            element = elements[0]
            center_x = element.x + element.width // 2
            center_y = element.y + element.height // 2
            confidence = element.confidence
            if confidence < self.MIN_CONFIDENCE_THRESHOLD:
                logger.warning(f"AI识别置信度 {confidence} < {self.MIN_CONFIDENCE_THRESHOLD}")
                return None
            return {
                "x": center_x,
                "y": center_y,
                "width": element.width,
                "height": element.height,
                "confidence": confidence,
                "type": element.type,
                "text": element.text,
            }
        except Exception as e:
            logger.error(f"AI视觉识别失败: {e}")
            return None

    async def _try_cached_click(
        self,
        cached: Dict[str, Any],
        description: str,
    ) -> Optional[MobileActionResult]:
        try:
            accessibility_id = cached.get("accessibility_id")
            resource_id = cached.get("resource_id")
            text = cached.get("text")
            element = await self.uiautomator.find_element(
                accessibility_id=accessibility_id,
                resource_id=resource_id,
                text=text,
            )
            if element and element.center:
                await self.adb.click(element.center["x"], element.center["y"])
                return MobileActionResult(
                    success=True,
                    action_type=MobileActionType.CLICK,
                    description=description,
                    coordinates=element.center,
                    cached_locator=cached,
                    used_cache=True,
                )
        except (UIAutomatorError, AdbError) as e:
            logger.warning(f"缓存定位执行失败: {e}")
        return None

    def _get_cached_locator(self, step_id: int) -> Optional[Dict[str, Any]]:
        locator = self.db.query(ElementLocator).filter(
            ElementLocator.step_id == step_id
        ).first()
        if not locator:
            return None
        if locator.source != "ai_mobile":
            return None
        cached = {}
        if locator.element_id:
            cached["resource_id"] = locator.element_id
        if locator.element_name:
            cached["accessibility_id"] = locator.element_name
        if locator.element_text:
            cached["text"] = locator.element_text
        if locator.ai_coordinate:
            cached["coordinates"] = locator.ai_coordinate
        if not cached:
            return None
        return cached

    async def _cache_locator(
        self,
        step_id: int,
        description: str,
        element_info: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            x = element_info.get("x", 0)
            y = element_info.get("y", 0)
            locator_data = await self.uiautomator.extract_locator_from_coordinates(x, y)
            resource_id = None
            accessibility_id = None
            element_text = None
            if locator_data:
                resource_id = locator_data.get("resource_id")
                accessibility_id = locator_data.get("accessibility_id")
                element_text = locator_data.get("text")
            existing = self.db.query(ElementLocator).filter(
                ElementLocator.step_id == step_id
            ).first()
            if existing:
                if resource_id:
                    existing.element_id = resource_id
                if accessibility_id:
                    existing.element_name = accessibility_id
                if element_text:
                    existing.element_text = element_text
                existing.ai_coordinate = {"x": x, "y": y}
                existing.source = "ai_mobile"
                self.db.commit()
                return locator_data
            locator = ElementLocator(
                step_id=step_id,
                element_description=description,
                css_selector=f"mobile://{resource_id or accessibility_id or ''}",
                ai_coordinate={"x": x, "y": y},
                ai_confidence=element_info.get("confidence", 0),
                source="ai_mobile",
            )
            if resource_id:
                locator.element_id = resource_id
            if accessibility_id:
                locator.element_name = accessibility_id
            if element_text:
                locator.element_text = element_text
            self.db.add(locator)
            self.db.commit()
            return locator_data
        except Exception as e:
            self.db.rollback()
            logger.warning(f"缓存定位信息失败: {e}")
            return None

    def _extract_input_text(self, description: str) -> Optional[str]:
        patterns = [
            r"输入[\"\"'](.+?)[\"\"']",
            r"输入(.+?)(?:到|进|入|$)",
            r"填写[\"\"'](.+?)[\"\"']",
            r"填写(.+?)(?:到|进|入|$)",
            r"键入[\"\"'](.+?)[\"\"']",
            r"type\s+[\"'](.+?)[\"']",
            r"input\s+[\"'](.+?)[\"']",
        ]
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()
        return None

    def _extract_input_target(self, description: str) -> Optional[str]:
        patterns = [
            r"在(.+?)中输入",
            r"在(.+?)里输入",
            r"在(.+?)上输入",
            r"在(.+?)输入",
            r"在(.+?)中填写",
            r"在(.+?)里填写",
        ]
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                return match.group(1).strip()
        return None

    def _extract_package_activity(self, description: str) -> Optional[tuple]:
        match = re.search(r"([\w.]+)/([\w.]+)", description)
        if match:
            package, activity = match.group(1), match.group(2)
            if re.match(r'^[a-zA-Z]', package) and re.match(r'^\.?[a-zA-Z]', activity):
                return package, activity
        return None
