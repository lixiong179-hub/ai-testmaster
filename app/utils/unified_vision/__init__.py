"""
统一视觉模型包

提供多模型适配的视觉AI能力，通过Mixin组合模式将请求构建、响应解析、
HTTP通信和API方法解耦为独立模块，支持OpenAI、百度、智谱等多种视觉模型。

多模型适配设计：
    核心思路是将模型差异隔离在RequestBuilderMixin和ResponseParserMixin中，
    上层API方法（APIMethodsMixin）无需关心底层模型差异。

    适配流程：
    1. RequestBuilderMixin: 根据model_type构建不同格式的请求Payload
    2. HTTPClientMixin: 统一发送HTTP请求（模型无关）
    3. ResponseParserMixin: 根据model_type解析不同格式的响应
    4. APIMethodsMixin: 提供元素识别、截图描述、操作验证等业务方法

Mixin模块：
    - RequestBuilderMixin: 请求构建（图片编码、Payload组装）
    - ResponseParserMixin: 响应解析（JSON提取、元素信息解析）
    - APIMethodsMixin: API方法（元素识别、截图描述、操作验证）
    - HTTPClientMixin: HTTP通信（请求发送、错误处理）

类型定义：
    - model_types.py: 模型类型枚举、元素信息数据类、模型提供商配置

使用示例：
    model = UnifiedVisionModel(model_type=VisionModelType.OPENAI)
    result = model.analyze_image(screenshot_bytes, "请描述这个页面")
"""
import os
from typing import Optional, Dict, Any

from app.utils.unified_vision.model_types import (
    VisionModelType, ElementInfo, ModelProviderConfig, MODEL_PROVIDER_CONFIGS,
)
from app.utils.unified_vision.request_builder_mixin import RequestBuilderMixin
from app.utils.unified_vision.response_parser_mixin import ResponseParserMixin
from app.utils.unified_vision.api_methods_mixin import APIMethodsMixin
from app.utils.unified_vision.http_client_mixin import HTTPClientMixin


class UnifiedVisionModel(
    RequestBuilderMixin,
    ResponseParserMixin,
    APIMethodsMixin,
    HTTPClientMixin,
):
    """统一视觉模型主类

    通过Mixin多重继承组合请求构建、响应解析、API方法和HTTP通信四大能力。
    对外提供统一的视觉分析接口，内部根据model_type自动适配不同模型提供商。

    配置优先级：
        1. 构造函数显式传入的参数（api_key/api_url/model_name）
        2. MODEL_PROVIDER_CONFIGS中该模型类型的默认配置
        3. 环境变量或settings中的配置

    Attributes:
        model_type: 模型类型枚举
        api_key: API密钥
        api_url: API端点URL
        model_name: 模型名称
        max_tokens: 最大生成token数
        temperature: 生成温度（0-1，越低越确定）
        timeout: 请求超时时间（秒）
    """

    def __init__(
        self,
        model_type: Optional[VisionModelType] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        timeout: int = 60,
    ):
        self.model_type = model_type or VisionModelType.OPENAI
        config = MODEL_PROVIDER_CONFIGS.get(self.model_type.value)

        # 按优先级获取配置：显式参数 > 提供商默认配置 > 环境变量/settings
        self.api_key = api_key or self._get_from_env_or_settings(
            config.api_key_env if config else "VISION_API_KEY",
            "VISION_API_KEY",
        )
        self.api_url = api_url or (config.api_url if config else "")
        self.model_name = model_name or (config.model_name if config else "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout


# 全局默认视觉模型实例 — 延迟初始化
_default_vision_model: Optional[UnifiedVisionModel] = None


def get_default_vision_model() -> UnifiedVisionModel:
    """获取全局默认视觉模型实例

    首次调用时创建默认配置的UnifiedVisionModel实例，
    后续调用返回同一实例。

    Returns:
        UnifiedVisionModel: 全局默认视觉模型实例
    """
    global _default_vision_model
    if _default_vision_model is None:
        _default_vision_model = UnifiedVisionModel()
    return _default_vision_model


def set_default_vision_model(model: UnifiedVisionModel) -> None:
    """设置全局默认视觉模型实例

    用于在应用启动时自定义默认模型的配置。

    Args:
        model: 要设置为默认的视觉模型实例
    """
    global _default_vision_model
    _default_vision_model = model


__all__ = [
    'UnifiedVisionModel',
    'VisionModelType',
    'ElementInfo',
    'ModelProviderConfig',
    'MODEL_PROVIDER_CONFIGS',
    'RequestBuilderMixin',
    'ResponseParserMixin',
    'APIMethodsMixin',
    'HTTPClientMixin',
    'get_default_vision_model',
    'set_default_vision_model',
]
