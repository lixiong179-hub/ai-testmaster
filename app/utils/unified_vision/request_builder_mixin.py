"""
统一视觉模型请求构建Mixin

提供根据模型类型构建不同格式API请求Payload的能力。
是UnifiedVisionModel多模型适配的核心模块，将模型差异封装在此层。

适配策略：
    - OpenAI/智谱/CUSTOM: 使用OpenAI标准格式（messages + content数组）
    - 百度: 使用百度自定义格式（无model字段，messages结构略有不同）

核心方法：
    - _build_request_payload: 根据model_type选择构建策略
    - _build_baidu_payload: 构建百度格式的请求Payload
    - _encode_image: 将图片字节数据编码为base64字符串

依赖：
    - app.utils.unified_vision.model_types: 模型类型枚举和配置
"""
import base64
from typing import Optional, Dict, Any

from app.utils.unified_vision.model_types import VisionModelType, ModelProviderConfig, MODEL_PROVIDER_CONFIGS


class RequestBuilderMixin:
    """请求构建Mixin

    根据模型类型构建不同格式的API请求Payload。
    OpenAI系列模型使用标准格式，百度模型使用自定义格式。
    """

    def _build_request_payload(
        self,
        image: bytes,
        prompt: str,
        model_type: Optional[VisionModelType] = None
    ) -> Dict[str, Any]:
        """构建API请求Payload

        根据model_type选择对应的构建策略：
        - BAIDU: 调用_build_baidu_payload构建百度格式
        - 其他: 构建OpenAI标准格式（含model字段和content数组）

        Args:
            image: 图片字节数据
            prompt: 分析提示词
            model_type: 模型类型，None时使用实例的model_type

        Returns:
            Dict[str, Any]: 构建好的请求Payload字典
        """
        effective_type = model_type or self.model_type
        if effective_type == VisionModelType.BAIDU:
            return self._build_baidu_payload(image, prompt)

        base64_image = self._encode_image(image)
        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def _build_baidu_payload(self, image: bytes, prompt: str) -> Dict[str, Any]:
        """构建百度文心大模型的请求Payload

        百度API与OpenAI格式的差异：
        - 无model字段（模型在URL中指定）
        - 无max_tokens字段
        - messages结构相同但顶层字段更少

        Args:
            image: 图片字节数据
            prompt: 分析提示词

        Returns:
            Dict[str, Any]: 百度格式的请求Payload字典
        """
        base64_image = self._encode_image(image)
        return {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            "temperature": self.temperature,
        }

    @staticmethod
    def _encode_image(image: bytes) -> str:
        """将图片字节数据编码为base64字符串

        Args:
            image: 图片的原始字节数据

        Returns:
            str: base64编码后的字符串
        """
        return base64.b64encode(image).decode("utf-8")
