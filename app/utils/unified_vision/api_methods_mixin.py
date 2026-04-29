"""
统一视觉模型API方法Mixin

提供面向业务的视觉分析API，包括元素识别、截图描述、
操作验证和元素中心点定位。是UnifiedVisionModel的高层接口。

核心方法：
    - recognize_elements: 识别页面截图中的目标元素
    - describe_screenshot: 描述页面截图的布局和内容
    - analyze_image: 通用图片分析（图片+提示词）
    - analyze_text: 纯文本分析（文本+提示词）
    - verify_action_result: 验证操作执行结果
    - find_element_center: 定位元素中心点坐标

依赖：
    - app.utils.unified_vision.model_types: ElementInfo数据类
    - app.utils.unified_vision.response_parser_mixin: 响应解析
"""
from typing import Optional, Dict, Any, List
from loguru import logger

from app.utils.unified_vision.model_types import ElementInfo


class APIMethodsMixin:
    """统一视觉模型API方法Mixin

    提供元素识别、截图描述、操作验证等业务级别的视觉分析API。
    所有方法内部调用RequestBuilderMixin构建请求、HTTPClientMixin发送请求、
    ResponseParserMixin解析响应，形成完整的调用链。
    """

    async def recognize_elements(self, screenshot: bytes, action_description: str) -> Optional[ElementInfo]:
        """识别页面截图中与操作描述匹配的目标元素

        Args:
            screenshot: 页面截图字节数据
            action_description: 操作描述（如"点击登录按钮"）

        Returns:
            Optional[ElementInfo]: 识别到的元素信息，识别失败返回None
        """
        prompt = self._get_element_recognition_prompt(action_description)
        response = self.analyze_image(screenshot, prompt)
        if response:
            from app.utils.unified_vision.response_parser_mixin import ResponseParserMixin
            return ResponseParserMixin._parse_element_recognition(response)
        return None

    async def describe_screenshot(self, screenshot: bytes) -> str:
        """描述页面截图的布局、元素和功能

        Args:
            screenshot: 页面截图字节数据

        Returns:
            str: 页面描述文本
        """
        prompt = "请详细描述这个页面的布局、元素和功能。"
        return self.analyze_image(screenshot, prompt)

    def analyze_image(self, image: bytes, prompt: str) -> str:
        """通用图片分析方法（同步）

        构建图片分析请求 → 发送HTTP请求 → 解析响应文本。
        是所有图片分析功能的基础方法。

        Args:
            image: 图片字节数据
            prompt: 分析提示词

        Returns:
            str: 模型返回的分析文本
        """
        payload = self._build_request_payload(image, prompt)
        response_text = self._make_request(payload)
        return self._parse_response(response_text)

    def analyze_text(self, text: str, prompt: str) -> str:
        """纯文本分析方法（同步，不涉及图片）

        将文本和提示词拼接后发送给模型，适用于文本理解和推理任务。

        Args:
            text: 待分析的文本内容
            prompt: 分析提示词

        Returns:
            str: 模型返回的分析文本
        """
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt + "\n\n" + text}
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        response_text = self._make_request(payload)
        return self._parse_response(response_text)

    async def verify_action_result(
        self,
        screenshot: bytes,
        action_description: str,
        expected_result: str
    ) -> Dict[str, Any]:
        """验证测试操作执行结果

        将操作后的截图与预期结果进行对比，判断操作是否成功。

        Args:
            screenshot: 操作后的页面截图
            action_description: 执行的操作描述
            expected_result: 预期结果描述

        Returns:
            Dict[str, Any]: 验证结果，包含：
                - success: 操作是否成功（bool）
                - reason: 判断理由（str）
        """
        prompt = self._get_action_verification_prompt(action_description, expected_result)
        response = self.analyze_image(screenshot, prompt)
        from app.utils.unified_vision.response_parser_mixin import ResponseParserMixin
        return ResponseParserMixin._parse_verification_result(response)

    async def find_element_center(self, screenshot: bytes, action_description: str) -> Optional[Dict[str, int]]:
        """定位元素中心点坐标

        先识别元素位置，再计算元素中心点坐标，用于模拟点击操作。

        Args:
            screenshot: 页面截图字节数据
            action_description: 操作描述（如"点击提交按钮"）

        Returns:
            Optional[Dict[str, int]]: 中心点坐标 {"x": int, "y": int}，识别失败返回None
        """
        element_info = await self.recognize_elements(screenshot, action_description)
        if element_info and element_info.is_valid:
            return {
                "x": element_info.x + element_info.width // 2,
                "y": element_info.y + element_info.height // 2,
            }
        return None

    @staticmethod
    def _get_element_recognition_prompt(action_description: str) -> str:
        """生成元素识别Prompt

        指导AI分析截图并返回目标元素的位置、类型和置信度。

        Args:
            action_description: 用户的操作描述

        Returns:
            str: 完整的元素识别Prompt
        """
        return f"""请仔细分析这个页面截图，精确定位以下操作的目标元素：

操作描述: {action_description}

请返回JSON格式：
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
- 坐标必须是整数
- 如果无法识别，返回 null
"""

    @staticmethod
    def _get_action_verification_prompt(action_description: str, expected_result: str) -> str:
        """生成操作验证Prompt

        指导AI对比操作后的截图与预期结果，判断操作是否成功。

        Args:
            action_description: 执行的操作描述
            expected_result: 预期结果描述

        Returns:
            str: 完整的操作验证Prompt
        """
        return f"""请验证以下测试步骤的执行结果：

操作: {action_description}
预期结果: {expected_result}

请返回JSON格式：
{{
    "success": true/false,
    "reason": "判断理由"
}}
"""
