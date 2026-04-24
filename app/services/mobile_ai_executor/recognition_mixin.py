"""移动端AI元素识别Mixin - AI视觉识别与缓存管理。"""
import re
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.utils.adb_controller import AdbController, AdbError
from app.utils.uiautomator_helper import UIAutomatorHelper, UIAutomatorError
from app.utils.unified_vision_model import UnifiedVisionModel
from app.models.element_locator import ElementLocator
from app.services.mobile_ai_executor.types import MobileRecognitionError


class MobileRecognitionMixin:
    """元素识别：AI视觉识别、缓存定位、缓存存储。"""

    MIN_CONFIDENCE_THRESHOLD = 0.7
    CACHE_CONFIDENCE_THRESHOLD = 0.8

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
                "x": center_x, "y": center_y,
                "width": element.width, "height": element.height,
                "confidence": confidence, "type": element.type, "text": element.text,
            }
        except Exception as e:
            logger.error(f"AI视觉识别失败: {e}")
            return None

    async def _try_cached_click(
        self, cached: Dict[str, Any], description: str
    ) -> Optional[Any]:
        from app.services.mobile_ai_executor.types import MobileActionResult, MobileActionType
        try:
            accessibility_id = cached.get("accessibility_id")
            resource_id = cached.get("resource_id")
            text = cached.get("text")
            element = await self.uiautomator.find_element(
                accessibility_id=accessibility_id, resource_id=resource_id, text=text,
            )
            if element and element.center:
                await self.adb.click(element.center["x"], element.center["y"])
                return MobileActionResult(
                    success=True, action_type=MobileActionType.CLICK, description=description,
                    coordinates=element.center, cached_locator=cached, used_cache=True,
                )
        except (UIAutomatorError, AdbError) as e:
            logger.warning(f"缓存定位执行失败: {e}")
        return None

    def _get_cached_locator(self, step_id: int) -> Optional[Dict[str, Any]]:
        locator = self.db.query(ElementLocator).filter(
            ElementLocator.step_id == step_id
        ).first()
        if not locator or locator.source != "ai_mobile":
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
        return cached if cached else None

    async def _cache_locator(
        self, step_id: int, description: str, element_info: Dict[str, Any]
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
