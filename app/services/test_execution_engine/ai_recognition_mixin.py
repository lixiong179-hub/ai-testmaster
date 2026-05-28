"""AI视觉识别Mixin - 通过视觉模型识别页面元素位置。
"""
import re
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.services.selector_registry import SelectorRegistry
from app.services.test_execution_engine.models import StepExecutionError
from app.utils.ai_client_parser import parse_ai_json_object


class AIRecognitionMixin:

    async def recognize_element_with_ai(
        self,
        screenshot: bytes,
        action_description: str
    ) -> Optional[Dict[str, Any]]:
        if not self.vision_model:
            logger.warning("视觉模型未初始化，跳过AI元素识别")
            return None

        prompt = f"""请分析这个页面截图，识别以下操作的目标元素：
操作描述: {action_description}

请返回目标元素的坐标信息（JSON格式）：
{{
    "x": 元素左上角x坐标,
    "y": 元素左上角y坐标,
    "width": 元素宽度,
    "height": 元素高度,
    "confidence": 识别置信度(0-1)
}}

注意：
- x, y 是相对于截图的像素坐标
- 如果无法识别，返回 null
"""
        try:
            response = self.vision_model.analyze_image(screenshot, prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                element_info = parse_ai_json_object(json_match.group())
                if element_info is not None:
                    confidence = element_info.get("confidence", 0)
                    if confidence < 0.9:
                        logger.warning(f"元素识别置信度较低: {confidence}")
                        return None
                    logger.info(f"AI识别元素成功: 置信度={confidence}")
                    return element_info
            return None
        except Exception as e:
            logger.error(f"AI元素识别失败: {str(e)}")
            return None

    async def verify_execution_result(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes,
        action_description: str,
        expected_result: str
    ) -> bool:
        if not self.vision_model:
            logger.warning("视觉模型未初始化，跳过AI验证")
            return True

        prompt = f"""请分析以下测试步骤的执行结果：

操作: {action_description}
预期结果: {expected_result}

请对比执行前后的页面截图，判断该步骤是否执行成功。

返回格式（JSON）：
{{
    "success": true/false,
    "reason": "判断理由"
}}
"""
        try:
            response = self.vision_model.analyze_image(after_screenshot, prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = parse_ai_json_object(json_match.group())
                if result is not None:
                    success = result.get("success", False)
                    reason = result.get("reason", "")
                    logger.info(f"AI验证结果: success={success}, reason={reason}")
                    return success
            logger.warning("AI验证响应无法解析，默认验证失败")
            return False
        except Exception as e:
            logger.error(f"AI验证执行失败: {str(e)}")
            return False

    async def smart_locate_with_ai_fallback(
        self,
        action_description: str,
        test_data: Optional[Dict[str, str]] = None,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

        action_text = self._substitute_parameters_in_action(
            action_description, test_data or {}
        )

        logger.info(f"智能元素定位开始: {action_text}")

        selector = self._get_element_selector(action_text)
        if selector:
            try:
                element_info = await self._locate_with_selector(selector)
                if element_info:
                    logger.info("策略1成功: 预定义选择器")
                    return element_info
            except Exception as e:
                logger.warning(f"策略1失败: 预定义选择器 - {e}")

        if self.locator_service:
            try:
                page_title = await self.browser.execute_javascript("document.title")
                element_info = await self.locator_service.smart_locate_element(
                    action_description=action_text,
                    page_title=page_title
                )
                if element_info:
                    logger.info("策略2成功: ElementLocatorService")
                    return element_info
            except Exception as e:
                logger.warning(f"策略2失败: ElementLocatorService - {e}")

        if self.enable_ai_recognition and self.vision_model:
            for attempt in range(max_retries):
                try:
                    screenshot = await self.browser.take_screenshot()
                    element_info = await self.recognize_element_with_ai(
                        screenshot, action_text
                    )
                    if element_info:
                        logger.info(f"策略3成功: AI识别 (尝试 {attempt + 1}/{max_retries})")
                        element_attrs = await self._get_element_attributes_from_coords(
                            element_info.get("x", 0),
                            element_info.get("y", 0),
                            element_info.get("width", 0),
                            element_info.get("height", 0)
                        )
                        if element_attrs:
                            css_selector = self._build_css_selector_from_attrs(element_attrs)
                            if css_selector:
                                element_info['css_selector'] = css_selector
                        return element_info
                except Exception as e:
                    logger.warning(f"策略3尝试 {attempt + 1} 失败: {e}")

        logger.warning("所有定位策略失败，无法定位元素")
        return None

    def _get_element_selector(self, action_text: str) -> Optional[str]:
        if not hasattr(self, '_selector_registry'):
            self._selector_registry = SelectorRegistry()
        return self._selector_registry.get_selector(None, action_text)

    @staticmethod
    def _build_css_selector_from_attrs(attrs: Dict[str, Any]) -> Optional[str]:
        if not attrs:
            return None
        element_id = attrs.get("id")
        if element_id:
            return f"#{element_id}"
        data_testid = attrs.get("data-testid")
        if data_testid:
            return f"[data-testid='{data_testid}']"
        name = attrs.get("name")
        if name:
            return f"[name='{name}']"
        tag = attrs.get("tag", "")
        element_class = attrs.get("class")
        if element_class and tag:
            classes = element_class.split()[:2]
            return f"{tag}.{'.'.join(classes)}"
        element_type = attrs.get("type")
        if element_type and tag:
            return f"{tag}[type='{element_type}']"
        if tag:
            return tag
        return None

    async def _locate_with_selector(self, selector: str) -> Optional[Dict[str, Any]]:
        try:
            first_selector = selector.split(',')[0].strip()
            element_info = await self.browser.execute_javascript("""
                (function() {
                    var el = document.querySelector(arguments[0]);
                    if (el) {
                        var rect = el.getBoundingClientRect();
                        return {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            css_selector: arguments[1],
                            confidence: 0.95
                        };
                    }
                    return null;
                })()
            """, first_selector, selector)
            if element_info:
                return element_info
            return None
        except Exception as e:
            logger.warning(f"选择器定位失败: {e}")
            return None

    async def _get_element_attributes_from_coords(
        self, x: int, y: int, width: int, height: int
    ) -> Optional[Dict[str, Any]]:
        center_x = x + width // 2
        center_y = y + height // 2
        try:
            attrs = await self.browser.execute_javascript("""
                (function() {
                    var element = document.elementFromPoint(arguments[0], arguments[1]);
                    if (!element) return null;
                    return {
                        tag: element.tagName ? element.tagName.toLowerCase() : '',
                        id: element.id || null,
                        name: element.getAttribute('name') || null,
                        class: element.className || null,
                        type: element.getAttribute('type') || null,
                        placeholder: element.getAttribute('placeholder') || null
                    };
                })()
            """, center_x, center_y)
            return attrs
        except Exception as e:
            logger.warning(f"获取元素属性失败: {e}")
            return None
