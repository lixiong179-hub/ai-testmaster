"""
统一视觉模型响应解析Mixin

提供根据模型类型解析不同格式API响应的能力。
与RequestBuilderMixin对称，将模型差异封装在此层。

适配策略：
    - OpenAI/智谱/CUSTOM: 从choices[0].message.content提取文本
    - 百度: 从result字段提取文本

核心方法：
    - _parse_response: 根据model_type选择解析策略
    - _parse_baidu_response: 解析百度格式的响应
    - _parse_element_recognition: 解析元素识别结果为ElementInfo
    - _parse_verification_result: 解析操作验证结果

依赖：
    - app.utils.unified_vision.model_types: ElementInfo数据类
"""
import json
import re
from typing import Optional, Dict, Any
from loguru import logger

from app.utils.unified_vision.model_types import ElementInfo, VisionModelType


class ResponseParserMixin:
    """响应解析Mixin

    根据模型类型解析不同格式的API响应，提取文本内容。
    同时提供元素识别和操作验证结果的专用解析方法。
    """

    def _parse_response(self, response_text: str, model_type: Optional[VisionModelType] = None) -> str:
        """解析模型API响应，提取文本内容

        根据model_type选择对应的解析策略：
        - BAIDU: 从result字段提取
        - 其他: 从choices[0].message.content提取（OpenAI标准格式）

        解析失败时原样返回response_text，确保不丢失数据。

        Args:
            response_text: API响应的原始文本
            model_type: 模型类型，None时使用实例的model_type

        Returns:
            str: 提取到的文本内容
        """
        effective_type = model_type or self.model_type
        if effective_type == VisionModelType.BAIDU:
            return self._parse_baidu_response(response_text)
        try:
            response_data = json.loads(response_text)
            if isinstance(response_data, dict):
                choices = response_data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    return message.get("content", "")
            return response_text
        except (json.JSONDecodeError, ValueError, TypeError):
            return response_text

    @staticmethod
    def _parse_baidu_response(response_text: str) -> str:
        """解析百度文心大模型的响应

        百度API响应格式：{"result": "文本内容", ...}
        与OpenAI的choices结构不同，直接从result字段提取。

        Args:
            response_text: API响应的原始文本

        Returns:
            str: 提取到的文本内容，解析失败原样返回
        """
        try:
            response_data = json.loads(response_text)
            if isinstance(response_data, dict):
                return response_data.get("result", "")
            return response_text
        except (json.JSONDecodeError, ValueError, TypeError):
            return response_text

    @staticmethod
    def _parse_element_recognition(response_text: str) -> Optional[ElementInfo]:
        """解析元素识别结果为ElementInfo数据类

        从模型返回的文本中提取JSON，构建ElementInfo实例。
        要求JSON包含x、y、width、height、element_type、confidence等字段。

        Args:
            response_text: 模型返回的元素识别结果文本

        Returns:
            Optional[ElementInfo]: 解析成功的元素信息，失败返回None
        """
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                return None
            data = json.loads(json_match.group())
            return ElementInfo(
                x=int(data.get("x", 0)),
                y=int(data.get("y", 0)),
                width=int(data.get("width", 0)),
                height=int(data.get("height", 0)),
                element_type=data.get("element_type", ""),
                placeholder=data.get("placeholder", ""),
                confidence=float(data.get("confidence", 0)),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"解析元素识别结果失败: {e}")
            return None

    @staticmethod
    def _parse_verification_result(response_text: str) -> Dict[str, Any]:
        """解析操作验证结果

        从模型返回的文本中提取JSON，获取验证成功/失败和判断理由。

        Args:
            response_text: 模型返回的验证结果文本

        Returns:
            Dict[str, Any]: 验证结果字典，包含：
                - success: 操作是否成功（bool）
                - reason: 判断理由（str）
                解析失败时返回 {"success": False, "reason": "错误信息"}
        """
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"success": False, "reason": "无法解析验证结果"}
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"解析验证结果失败: {e}")
            return {"success": False, "reason": str(e)}
