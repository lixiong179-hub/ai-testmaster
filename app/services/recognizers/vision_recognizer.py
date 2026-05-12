
"""视觉识别器 - 使用AI视觉模型识别页面元素。
"""
import json
import re
from typing import Optional, Dict, Any, List

from loguru import logger

from app.interfaces.element_recognizer import ElementRecognizer, RecognitionResult
from app.utils.unified_vision_model import UnifiedVisionModel


class VisionRecognizer(ElementRecognizer):

    def __init__(self, vision_model: UnifiedVisionModel, confidence_threshold: float = 0.8) -> None:
        self.vision_model = vision_model
        self.confidence_threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "vision"

    async def is_available(self) -> bool:
        return self.vision_model is not None

    async def recognize(self, browser, operation_description: str, action_type: Optional[str] = None) -> RecognitionResult:
        page = browser._page if hasattr(browser, '_page') else browser
        try:
            screenshot = await browser.take_screenshot()
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return RecognitionResult(
                locator_type="vision",
                locator_value="",
                confidence=0,
                raw_result={"error": "截图失败"}
            )

        if not screenshot:
            return RecognitionResult(
                locator_type="vision",
                locator_value="",
                confidence=0
            )

        prompt = self._build_recognition_prompt(operation_description, action_type)

        try:
            response = self.vision_model.analyze_image(screenshot, prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                element_info = json.loads(json_match.group())
                confidence = element_info.get("confidence", 0)
                if confidence < self.confidence_threshold:
                    logger.warning(f"元素识别置信度较低: {confidence} < {self.confidence_threshold}")
                    return RecognitionResult(
                        locator_type="vision",
                        locator_value="",
                        confidence=confidence,
                        raw_result=element_info
                    )

                coordinate = self._normalize_coordinate(element_info)
                css_selector = None
                element_attrs = None
                try:
                    element_attrs = await self._get_element_attributes(page, coordinate)
                    if element_attrs:
                        css_selector = self._generate_css_selector(element_attrs)
                except Exception as e:
                    logger.warning(f"获取元素属性失败: {e}")

                return RecognitionResult(
                    locator_type="vision",
                    locator_value=css_selector or json.dumps(coordinate),
                    confidence=confidence,
                    raw_result=element_info,
                    element_info={
                        **coordinate,
                        "css_selector": css_selector,
                        "element_attrs": element_attrs
                    }
                )

            return RecognitionResult(
                locator_type="vision",
                locator_value="",
                confidence=0
            )

        except json.JSONDecodeError as e:
            logger.error(f"AI响应JSON解析失败: {e}")
            return RecognitionResult(locator_type="vision", locator_value="", confidence=0)
        except Exception as e:
            logger.error(f"元素识别发生错误: {e}")
            return RecognitionResult(locator_type="vision", locator_value="", confidence=0, raw_result={"error": "识别失败"})

    async def batch_recognize(self, browser, operations: List[str]) -> List[RecognitionResult]:
        results = []
        for op in operations:
            result = await self.recognize(browser, op)
            results.append(result)
        return results

    def _build_recognition_prompt(self, action_description: str, action_type: Optional[str] = None) -> str:
        base_prompt = f"请仔细分析这个页面截图，精确定位以下操作的目标元素：\n\n操作描述: {action_description}\n\n"

        login_keywords = ["登录", "用户名", "密码", "验证码", "login", "username", "password"]
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
{
    "x": 元素左上角x坐标（整数）,
    "y": 元素左上角y坐标（整数）,
    "width": 元素宽度（整数）,
    "height": 元素高度（整数）,
    "element_type": "input|button|text",
    "placeholder": "placeholder文本或标签文本",
    "confidence": 识别置信度(0-1),
    "reasoning": "为什么选择了这个元素"
}

注意：
- x, y 是相对于截图左上角的像素坐标
- 坐标必须是整数，不能是数组
- 如果无法识别，返回 null
- 必须根据操作描述精确匹配对应的元素，不要混淆
"""
        return base_prompt

    @staticmethod
    def _normalize_coordinate(element_info: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key in ["x", "y", "width", "height"]:
            val = element_info.get(key, 0)
            if val is None:
                val = 0
            if isinstance(val, list):
                val = val[0] if val else 0
            result[key] = val
        return result

    async def _get_element_attributes(self, page, coordinate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        x = coordinate.get("x", 0) + coordinate.get("width", 0) // 2
        y = coordinate.get("y", 0) + coordinate.get("height", 0) // 2
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
            attrs = await page.execute_javascript(js_code, x, y)
            return attrs or {}
        except Exception as e:
            logger.error(f"获取元素属性失败: {e}")
            return {}

    @staticmethod
    def _generate_css_selector(element_attrs: Dict[str, Any]) -> Optional[str]:
        if not element_attrs:
            return None
        tag = element_attrs.get("tag", "")
        eid = element_attrs.get("id")
        if eid:
            return f"#{eid}"
        name = element_attrs.get("name")
        if name:
            return f"[name='{name}']"
        data_testid = element_attrs.get("data-testid")
        if data_testid:
            return f"[data-testid='{data_testid}']"
        text = element_attrs.get("text")
        if text and tag:
            safe_text = text[:20].strip()
            if safe_text:
                return f"{tag}:has-text('{safe_text}')"
        classes = element_attrs.get("class")
        if classes and tag:
            class_list = classes.split()[:2]
            return f"{tag}.{'.'.join(class_list)}"
        return tag if tag else None
