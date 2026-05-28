import base64
import time
import requests
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from app.utils.unified_vision_model._types import (
    VisionModelType,
    ElementInfo,
    ModelProviderConfig,
    MODEL_PROVIDER_CONFIGS,
)


class _VisionCoreMixin:
    def _init_core(
        self,
        model_type: VisionModelType = VisionModelType.MIMO,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 2,
        timeout: int = 300,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        self.model_type = model_type
        self.provider_config = MODEL_PROVIDER_CONFIGS[model_type]

        self.api_key = api_key or self._get_from_env_or_settings(
            self.provider_config.api_key_env
        )
        self.base_url = base_url or self._get_from_env_or_settings(
            self.provider_config.base_url_env,
            self.provider_config.default_base_url,
        )
        self.model_name = model_name or self._get_from_env_or_settings(
            self.provider_config.model_name_env,
            self.provider_config.default_model_name,
        )

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

        if not self.api_key:
            logger.warning(f"{model_type.value} API Key 未配置，视觉识别功能将不可用")

    def _get_from_env_or_settings(self, env_name: str, default: str = "") -> str:
        import os
        from app.core.config import settings

        value = os.getenv(env_name)
        if value:
            return value

        return getattr(settings, env_name, default)

    def _encode_image(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode('utf-8')

    def _build_request_payload(
        self,
        system_prompt: str,
        user_content: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        content = []
        for item in user_content:
            if item.get('type') == 'image':
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{item['image']}"
                    }
                })
            else:
                content.append({
                    "type": "text",
                    "text": item.get('text', '')
                })

        if self.model_type == VisionModelType.BAIDU:
            return self._build_baidu_payload(system_prompt, user_content, temperature)

        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            "temperature": temperature or self.temperature,
            "max_tokens": self.max_tokens
        }

    def _build_baidu_payload(
        self,
        system_prompt: str,
        user_content: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        messages = [{"role": "system", "content": system_prompt}]

        content_parts = []
        for item in user_content:
            if item.get('type') == 'image':
                content_parts.append("[图片]")
            else:
                content_parts.append(item.get('text', ''))

        messages.append({"role": "user", "content": "\n".join(content_parts)})

        return {
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_output_tokens": self.max_tokens
        }

    def _parse_response(self, response: Dict[str, Any]) -> Optional[str]:
        if self.model_type == VisionModelType.BAIDU:
            return self._parse_baidu_response(response)

        if not isinstance(response, dict):
            logger.error(f"解析响应失败: 响应非dict类型: {type(response).__name__}")
            return None

        if "error" in response:
            error_info = response["error"]
            error_msg = error_info.get("message", str(error_info)) if isinstance(error_info, dict) else str(error_info)
            logger.error(f"API返回错误: {error_msg}")
            return None

        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            resp_keys = list(response.keys()) if isinstance(response, dict) else 'N/A'
            logger.error(f"解析响应失败: {e}, 响应键: {resp_keys}")
            return None

    def _parse_baidu_response(self, response: Dict[str, Any]) -> Optional[str]:
        try:
            return response.get("result", "")
        except Exception as e:
            logger.error(f"解析文心一言响应失败: {e}")
            return None

    def _make_request(self, payload: Dict[str, Any]) -> Optional[str]:
        if not self.api_key:
            logger.error(f"{self.model_type.value} API Key 未配置")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        endpoint = self.provider_config.api_endpoint
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                logger.info(f"{self.model_type.value} API 请求 - 尝试 {attempt + 1}/{self.max_retries}")
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()
                content = self._parse_response(result)
                logger.info(f"{self.model_type.value} API 请求成功")
                return content

            except requests.RequestException as e:
                logger.error(f"{self.model_type.value} API 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                else:
                    self._handle_request_error(e)
                    return None
            except Exception as e:
                logger.error(f"{self.model_type.value} API 请求异常: {str(e)}")
                return None

        return None

    def _handle_request_error(self, error: requests.RequestException):
        model_name = self.model_type.value

        status_code = None
        if hasattr(error, 'response') and error.response is not None:
            status_code = error.response.status_code

        if status_code == 401:
            logger.error(f"{model_name} API 认证失败，请检查 API Key")
        elif status_code == 429:
            logger.error(f"{model_name} API 请求频率过高，请稍后重试")
        elif status_code == 403:
            logger.error(f"{model_name} API 权限不足")
        elif status_code == 404:
            logger.error(f"{model_name} API 地址错误")
        elif status_code is not None and status_code >= 500:
            logger.error(f"{model_name} API 服务端错误 (HTTP {status_code})")
        elif "timeout" in str(error).lower():
            logger.error(f"{model_name} API 请求超时")
        else:
            logger.error(f"{model_name} API 请求失败: {error}")
