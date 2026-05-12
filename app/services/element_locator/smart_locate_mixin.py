"""智能定位Mixin - AI+规则混合的智能元素定位策略。
"""
from typing import Optional, Dict, Any
from loguru import logger

from app.services.selector_registry import SelectorRegistry
from app.services.recognizers.mcp_recognizer import MCPRecognizer
from app.interfaces.element_recognizer import RecognitionResult
from app.core.config import settings
from app.core.constants import LOGIN_KEYWORDS


class SmartLocateMixin:

    async def smart_locate_element(
        self,
        action_description: str,
        page_title: Optional[str] = None,
        action_type: Optional[str] = None,
        input_value: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        logger.info(f"智能定位元素: {action_description}")

        registry = SelectorRegistry()
        css_selector = registry.get_selector(page_title, action_description)

        if css_selector:
            logger.info(f"使用预定义选择器: {css_selector}")
            try:
                first_selector = css_selector.split(',')[0].strip()
                element_exists = await self.browser.execute_javascript("""
                    (function() {
                        return document.querySelector(arguments[0]) !== null;
                    })()
                """, first_selector)

                if element_exists:
                    element_info = await self.browser.execute_javascript("""
                        (function() {
                            var el = document.querySelector(arguments[0]);
                            if (el) {
                                var rect = el.getBoundingClientRect();
                                return {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    css_selector: arguments[1],
                                    confidence: 0.95
                                };
                            }
                            return null;
                        })()
                    """, first_selector, css_selector)

                    if element_info:
                        logger.info(f"预定义选择器定位成功: {element_info}")
                        return element_info
            except Exception as e:
                logger.warning(f"预定义选择器失败: {e}")

        logger.info(f"预定义选择器失败，使用{self.recognizer.name}识别器")
        recognition_result = await self.recognizer.recognize(self.browser, action_description, action_type=action_type)

        if recognition_result and recognition_result.is_valid:
            if recognition_result.locator_type == "vision" and recognition_result.element_info:
                element_info = recognition_result.element_info
                if element_info.get("css_selector"):
                    logger.info(f"AI视觉定位成功: {element_info}")
                    return element_info
                element_attrs = await self._get_element_attributes(element_info)
                css_selector = self._generate_css_selector(element_attrs)
                element_info['css_selector'] = css_selector
                logger.info(f"AI视觉定位成功: {element_info}")
                return element_info
            elif recognition_result.locator_type in ("role", "text", "css", "ref"):
                result_info = {
                    "locator_type": recognition_result.locator_type,
                    "locator_value": recognition_result.locator_value,
                    "confidence": recognition_result.confidence,
                    "css_selector": recognition_result.locator_value if recognition_result.locator_type == "css" else None
                }
                if recognition_result.element_info:
                    result_info.update(recognition_result.element_info)
                if action_type and self._should_direct_execute(action_type):
                    executed = await self.direct_execute_action(recognition_result, action_type, input_value)
                    if executed:
                        result_info["_direct_executed"] = True
                logger.info(f"MCP定位成功: {result_info}")
                return result_info

        logger.error(f"无法定位元素: {action_description}")
        return None

    def _should_direct_execute(self, action_type: str) -> bool:
        if not getattr(settings, 'MCP_DIRECT_EXECUTION_ENABLED', False):
            return False
        if not isinstance(self.recognizer, MCPRecognizer):
            return False
        allowed_types = getattr(settings, 'MCP_EXECUTION_OPERATION_TYPES', 'click,type,hover,select').split(',')
        return action_type in allowed_types

    async def direct_execute_action(self, recognition_result: RecognitionResult, action_type: str = "click", input_value: Optional[str] = None) -> bool:
        if not isinstance(self.recognizer, MCPRecognizer):
            return False
        try:
            return await self.recognizer.execute_action(recognition_result, action_type, input_value)
        except Exception as e:
            logger.warning(f"MCP直执失败: {e}")
            return False

    async def _get_element_attributes(
        self,
        element_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        x = element_info.get("x", 0) + element_info.get("width", 0) // 2
        y = element_info.get("y", 0) + element_info.get("height", 0) // 2

        js_code = """
        (function() {
            var element = document.elementFromPoint(arguments[0], arguments[1]);
            if (!element) return null;

            return {
                tag: element.tagName.toLowerCase(),
                id: element.id || null,
                name: element.getAttribute('name') || null,
                class: element.className || null,
                text: element.textContent ? element.textContent.trim().substring(0, 100) : null,
                'data-testid': element.getAttribute('data-testid') || null,
                'data-id': element.getAttribute('data-id') || null,
                type: element.getAttribute('type') || null,
                placeholder: element.getAttribute('placeholder') || null
            };
        })()
        """

        try:
            attrs = await self.browser.execute_javascript(js_code, x, y)
            return attrs or {}
        except TimeoutError as e:
            logger.error(f"获取元素属性超时: {str(e)}")
            return {}
        except ConnectionError as e:
            logger.error(f"浏览器连接失败: {str(e)}")
            return {}
        except Exception as e:
            logger.exception(f"获取元素属性发生未知错误: {str(e)}")
            return {}

    def _build_recognition_prompt(self, action_description: str, action_type: Optional[str] = None) -> str:
        base_prompt = f"请仔细分析这个页面截图，精确定位以下操作的目标元素：\n\n操作描述: {action_description}\n\n"

        login_keywords = LOGIN_KEYWORDS
        is_login_page = any(kw in action_description.lower() for kw in login_keywords)

        if is_login_page:
            base_prompt += """重要提示：
1. 这是一个登录表单页面，包含多个输入框（用户名、密码、验证码）
2. 请根据操作描述中的关键词，准确找到对应的输入框
3. 用户名输入框通常有"用户名"标签或用户图标
4. 密码输入框通常有"密码"标签或锁图标，输入内容会显示为圆点
5. 验证码输入框通常在验证码图片旁边

"""
        else:
            base_prompt += """请根据操作描述中的关键词，在页面中找到对应的目标元素。
注意区分相似元素，确保选择正确的目标。

"""

        if action_type == "verify":
            base_prompt += """这是一个验证步骤，请定位需要验证的目标元素的位置和状态。
重点关注元素的显示文本和位置。

"""

        base_prompt += """请返回JSON格式：
{{
    "x": 元素左上角x坐标（整数）,
    "y": 元素左上角y坐标（整数）,
    "width": 元素宽度（整数）,
    "height": 元素高度（整数）,
    "element_type": "input|button|text",
    "placeholder": "placeholder文本或标签文本",
    "confidence": 识别置信度(0-1),
    "reasoning": "为什么选择了这个元素"
}}

注意：
- x, y 是相对于截图左上角的像素坐标
- 坐标必须是整数，不能是数组
- 如果无法识别，返回 null
- 必须根据操作描述精确匹配对应的元素，不要混淆
"""
        return base_prompt
