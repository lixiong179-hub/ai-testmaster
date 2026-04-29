"""
统一视觉模型HTTP客户端Mixin

提供与视觉模型API的HTTP通信能力，包括请求发送、错误处理和配置获取。
使用httpx作为HTTP客户端，支持超时控制和错误分类。

核心方法：
    - _make_request: 发送HTTP POST请求到模型API
    - _handle_request_error: 统一错误处理和消息格式化
    - _get_from_env_or_settings: 从环境变量或settings获取配置

错误处理策略：
    - 超时错误: 抛出ConnectionError，包含超时时间信息
    - HTTP状态码错误: 抛出ConnectionError，包含状态码信息
    - 网络错误: 抛出ConnectionError，包含网络错误详情

依赖：
    - httpx: HTTP客户端库
    - app.utils.unified_vision.model_types: 模型类型和配置
"""
import os
import json
import httpx
from typing import Optional, Dict, Any
from loguru import logger

from app.utils.unified_vision.model_types import VisionModelType, MODEL_PROVIDER_CONFIGS


class HTTPClientMixin:
    """HTTP客户端Mixin

    提供与视觉模型API通信的HTTP能力。
    使用httpx同步客户端发送请求，支持超时控制和分类错误处理。
    """

    def _make_request(self, payload: Dict[str, Any]) -> str:
        """发送HTTP POST请求到模型API

        使用httpx发送JSON格式的POST请求，携带Bearer Token认证。
        请求失败时根据错误类型生成友好的错误消息。

        Args:
            payload: 请求Payload字典

        Returns:
            str: API响应的原始文本

        Raises:
            ConnectionError: 请求超时、HTTP错误或网络错误
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # 智谱AI使用相同的Bearer格式，此处预留差异化处理入口
        if self.model_type == VisionModelType.ZHIPU:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.api_url, json=payload, headers=headers)
                response.raise_for_status()
                return response.text
        except httpx.TimeoutException as e:
            error_msg = self._handle_request_error(e, "timeout")
            raise ConnectionError(error_msg) from e
        except httpx.HTTPStatusError as e:
            error_msg = self._handle_request_error(e, f"http_{e.response.status_code}")
            raise ConnectionError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = self._handle_request_error(e, "network")
            raise ConnectionError(error_msg) from e

    @staticmethod
    def _handle_request_error(error: Exception, error_type: str) -> str:
        """统一处理HTTP请求错误，生成友好的错误消息

        Args:
            error: 原始异常对象
            error_type: 错误类型标识（timeout/network/http_XXX）

        Returns:
            str: 格式化的错误消息
        """
        error_messages = {
            "timeout": f"请求超时: {str(error)}",
            "network": f"网络错误: {str(error)}",
        }
        if error_type.startswith("http_"):
            status_code = error_type.replace("http_", "")
            return f"HTTP错误 {status_code}: {str(error)}"
        return error_messages.get(error_type, f"请求失败: {str(error)}")

    @staticmethod
    def _get_from_env_or_settings(env_key: str, settings_attr: str, default: str = "") -> str:
        """从环境变量或settings获取配置值

        优先级：环境变量 > settings配置 > 默认值

        Args:
            env_key: 环境变量名
            settings_attr: settings中的属性名
            default: 默认值

        Returns:
            str: 获取到的配置值
        """
        value = os.environ.get(env_key, "")
        if value:
            return value
        try:
            from app.core.config import settings
            return getattr(settings, settings_attr, default)
        except Exception:
            return default
