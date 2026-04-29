"""定位记录Mixin - 记录和更新元素定位结果。
"""
from typing import Optional, Dict, Any
from loguru import logger

from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.models.test_case import TestStep, TestCasePreconditionStep


class LocatorRecordMixin:

    async def record_locator(
        self,
        step_id: int,
        action_description: str,
        screenshot: Optional[bytes] = None,
        source: str = "ai"
    ) -> Optional[ElementLocator]:
        logger.info(f"开始记录步骤 {step_id} 的元素定位信息")

        if screenshot is None:
            screenshot = await self.browser.take_screenshot()

        element_info = await self.recognizer.recognize(self.browser, action_description)
        element_info = element_info.element_info if element_info and element_info.is_valid else None
        if not element_info:
            logger.warning(f"步骤 {step_id}: AI无法识别目标元素")
            return None

        logger.info(f"步骤 {step_id}: AI识别到元素坐标: {element_info}")

        element_attrs = await self._get_element_attributes(element_info)
        logger.info(f"步骤 {step_id}: 获取到元素属性: {element_attrs}")

        css_selector = self._generate_css_selector(element_attrs)
        logger.info(f"步骤 {step_id}: 生成CSS选择器: {css_selector}")

        coordinate = self._normalize_coordinate(element_info)

        locator = ElementLocator(
            step_id=step_id,
            element_description=action_description,
            element_type=element_attrs.get("tag"),
            css_selector=css_selector,
            xpath=self._generate_xpath(element_attrs),
            element_id=element_attrs.get("id"),
            element_name=element_attrs.get("name"),
            element_class=element_attrs.get("class"),
            element_text=element_attrs.get("text"),
            ai_coordinate=coordinate,
            ai_confidence=element_info.get("confidence", 0),
            source=source
        )

        self.db.add(locator)
        self.db.commit()
        self.db.refresh(locator)

        step = self.db.query(TestStep).filter(TestStep.id == step_id).first()
        if step:
            step.has_locator = 1
            step.locator_status = LocatorStatus.RECORDED.value
            self.db.commit()

        logger.info(f"步骤 {step_id}: 元素定位信息已保存，ID={locator.id}")
        return locator

    async def record_precondition_step_locator(
        self,
        precondition_step_id: int,
        action_description: str,
        action_type: Optional[str] = None,
        screenshot: Optional[bytes] = None
    ) -> Optional[ElementLocator]:
        logger.info(f"开始记录前置条件步骤 {precondition_step_id} 的元素定位信息")

        if screenshot is None:
            screenshot = await self.browser.take_screenshot()

        recognition_result = await self.recognizer.recognize(self.browser, action_description, action_type=action_type)
        element_info = recognition_result.element_info if recognition_result and recognition_result.is_valid else None
        if not element_info:
            logger.warning(f"前置条件步骤 {precondition_step_id}: AI无法识别目标元素")
            return None

        element_attrs = await self._get_element_attributes(element_info)
        css_selector = self._generate_css_selector(element_attrs)
        coordinate = self._normalize_coordinate(element_info)

        locator = ElementLocator(
            step_id=None,
            precondition_step_id=precondition_step_id,
            element_description=action_description,
            element_type=element_attrs.get("tag"),
            css_selector=css_selector,
            xpath=self._generate_xpath(element_attrs),
            element_id=element_attrs.get("id"),
            element_name=element_attrs.get("name"),
            element_class=element_attrs.get("class"),
            element_text=element_attrs.get("text"),
            ai_coordinate=coordinate,
            ai_confidence=element_info.get("confidence", 0),
            source="ai"
        )

        self.db.add(locator)
        self.db.commit()
        self.db.refresh(locator)

        pc_step = self.db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.id == precondition_step_id
        ).first()
        if pc_step:
            pc_step.has_locator = 1
            pc_step.locator_status = LocatorStatus.RECORDED.value
            self.db.commit()

        logger.info(f"前置条件步骤 {precondition_step_id}: 元素定位信息已保存，ID={locator.id}")
        return locator

    async def _recognize_element(
        self,
        screenshot: bytes,
        action_description: str,
        action_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        logger.warning("_recognize_element已废弃，请使用recognizer.recognize()")
        from app.services.recognizers.vision_recognizer import VisionRecognizer
        if isinstance(self.recognizer, VisionRecognizer):
            result = await self.recognizer.recognize(self.browser, action_description, action_type)
        else:
            vision_recognizer = VisionRecognizer(self.vision_model, self.confidence_threshold)
            result = await vision_recognizer.recognize(self.browser, action_description, action_type)
        if result and result.is_valid:
            return result.element_info
        return None
