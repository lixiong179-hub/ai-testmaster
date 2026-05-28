import json
import re
from typing import List, Dict, Any, Optional
from loguru import logger

from app.utils.unified_vision_model._types import ElementInfo
from app.utils.ai_client_parser import fix_common_json_issues, clean_json_string, parse_ai_json_object


class _VisionApiMixin:
    def recognize_elements(
        self,
        screenshot: bytes,
        description: str,
        min_confidence: float = 0.9,
    ) -> List[ElementInfo]:
        if not self.api_key:
            logger.error(f"{self.model_type.value} API Key 未配置")
            return []

        encoded_image = self._encode_image(screenshot)

        system_prompt = self._get_element_recognition_prompt()
        user_prompt = f"请识别截图中与'{description}'相关的所有可交互元素"

        user_content = [
            {"type": "image", "image": encoded_image},
            {"type": "text", "text": user_prompt}
        ]

        payload = self._build_request_payload(system_prompt, user_content)
        content = self._make_request(payload)

        if not content:
            return []

        return self._parse_element_recognition(content, min_confidence)

    def describe_screenshot(self, screenshot: bytes) -> str:
        if not self.api_key:
            return "视觉模型未配置"

        encoded_image = self._encode_image(screenshot)

        system_prompt = "你是一个专业的UI测试工程师，请详细描述当前页面内容。"
        user_content = [
            {"type": "image", "image": encoded_image},
            {"type": "text", "text": "请描述这个页面的主要内容、布局和可交互元素"}
        ]

        payload = self._build_request_payload(system_prompt, user_content)
        result = self._make_request(payload)

        return result or "无法描述页面内容"

    def analyze_image(self, screenshot: bytes, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            return "视觉模型未配置"

        encoded_image = self._encode_image(screenshot)

        if system_prompt is None:
            system_prompt = "你是一个专业的UI测试工程师，擅长分析页面截图。"

        user_content = [
            {"type": "image", "image": encoded_image},
            {"type": "text", "text": prompt}
        ]

        payload = self._build_request_payload(system_prompt, user_content)
        result = self._make_request(payload)

        if result:
            logger.info(f"analyze_image 返回结果长度: {len(result)}")
        return result or "无法分析图片内容"

    def verify_action_result(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes,
        action_description: str,
        expected_result: str,
    ) -> tuple:
        if not self.api_key:
            return (False, "视觉模型未配置")

        before_encoded = self._encode_image(before_screenshot)
        after_encoded = self._encode_image(after_screenshot)

        system_prompt = self._get_action_verification_prompt()
        user_content = [
            {"type": "text", "text": f"操作: {action_description}\n预期结果: {expected_result}"},
            {"type": "image", "image": before_encoded},
            {"type": "image", "image": after_encoded},
            {"type": "text", "text": "请验证操作是否成功，以JSON格式返回结果"}
        ]

        payload = self._build_request_payload(system_prompt, user_content)
        content = self._make_request(payload)

        if not content:
            return (False, "无法验证操作结果")

        return self._parse_verification_result(content)

    def analyze_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        if not self.api_key:
            return "视觉模型未配置"

        if system_prompt is None:
            system_prompt = "你是一个专业的UI测试工程师。"

        user_content = [{"type": "text", "text": prompt}]

        payload = self._build_request_payload(system_prompt, user_content, temperature)
        result = self._make_request(payload)

        return result or "无法分析文本内容"

    def _get_element_recognition_prompt(self) -> str:
        return """你是一个专业的UI测试工程师，擅长识别网页和移动应用界面元素。

请分析提供的截图，识别出所有可交互元素。

对于每个识别到的元素，请提供以下信息（JSON格式）：
[
  {
    "type": "元素类型(button/input/link等)",
    "text": "元素文本内容",
    "x": 元素左上角x坐标(int),
    "y": 元素左上角y坐标(int),
    "width": 元素宽度(int),
    "height": 元素高度(int),
    "confidence": 识别置信度0-1(float)
  }
]

只返回JSON数组，不要其他解释文字。"""

    def _get_action_verification_prompt(self) -> str:
        return """你是一个专业的UI测试验证专家。

请比较操作前后的截图，验证操作是否达到预期效果。

请以JSON格式返回验证结果：
{
  "success": true/false,
  "reason": "验证结果的详细说明"
}

只返回JSON对象，不要其他解释文字。"""

    def _parse_element_recognition(self, content: str, min_confidence: float) -> List[ElementInfo]:
        elements_data = None
        try:
            elements_data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', content)
            if json_match:
                raw = json_match.group(0)
                for fix_fn in (fix_common_json_issues, clean_json_string):
                    fixed = fix_fn(raw)
                    if fixed:
                        try:
                            elements_data = json.loads(fixed)
                            break
                        except json.JSONDecodeError:
                            continue
                if elements_data is None:
                    try:
                        elements_data = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.error("元素识别失败：无法解析JSON响应")
                        return []
            else:
                logger.error("元素识别失败：响应中未找到JSON")
                return []

        elements = []
        if isinstance(elements_data, list):
            for elem_data in elements_data:
                try:
                    element = ElementInfo(
                        type=elem_data.get('type', 'unknown'),
                        text=elem_data.get('text', ''),
                        x=int(elem_data.get('x', 0)),
                        y=int(elem_data.get('y', 0)),
                        width=int(elem_data.get('width', 0)),
                        height=int(elem_data.get('height', 0)),
                        confidence=float(elem_data.get('confidence', 0))
                    )
                    if element.confidence >= min_confidence:
                        elements.append(element)
                except (ValueError, TypeError) as e:
                    logger.warning(f"解析元素数据失败: {elem_data}, 错误: {e}")
                    continue

        elements.sort(key=lambda x: x.confidence, reverse=True)
        logger.info(f"元素识别成功，找到 {len(elements)} 个元素")
        return elements

    def _parse_verification_result(self, content: str) -> tuple:
        if not content:
            return (False, "无法验证操作结果")

        result = parse_ai_json_object(content)
        if result is None:
            json_match = re.search(r'\{\s*"success"[\s\S]*\}', content)
            if json_match:
                result = parse_ai_json_object(json_match.group(0))
        if result is None:
            return (False, "无法解析验证结果")

        success = result.get('success', False)
        reason = result.get('reason', '无说明')

        return (success, reason)

    def find_element_center(self, element: ElementInfo) -> tuple:
        center_x = element.x + element.width // 2
        center_y = element.y + element.height // 2
        return (center_x, center_y)
