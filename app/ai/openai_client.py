"""
OpenAI 兼容 AI Client 实现

本模块实现 AIClient Protocol，封装 OpenAI SDK 调用逻辑：
    - 从全局配置读取 API 密钥、端点、模型名
    - 支持 system prompt、JSON Schema 约束、temperature/max_tokens 覆盖
    - 自动记录调用日志（通过 call_log 模块）
    - 异常映射为 AIServiceError 体系

依赖关系：
    - openai.OpenAI : OpenAI SDK
    - app.core.config.settings : 全局配置
    - app.ai.client : AIResponse, TokenUsage
    - app.ai.call_log : record_call
    - app.utils.ai_client_core : AIServiceError, _detect_ai_error
"""
import json
import time
from typing import Any, Dict, Optional

from loguru import logger
from openai import OpenAI

from app.ai.client import AIResponse, TokenUsage
from app.core.config import settings


# DeepSeek 定价（美元/1K tokens），可按实际模型调整
_COST_PER_1K_PROMPT = 0.0014
_COST_PER_1K_COMPLETION = 0.0028


class OpenAIClient:
    """OpenAI 兼容 AI Client 实现

    通过 OpenAI SDK 调用兼容 API（DeepSeek 等），实现 AIClient Protocol。

    Attributes:
        model: 默认模型名称
        api_key: API 密钥
        base_url: API 基础 URL
        temperature: 默认生成温度
        max_tokens: 默认最大输出 Token 数
        max_retries: 最大重试次数
    """

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
    ) -> None:
        self.model = model or settings.AI_MODEL_NAME
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.base_url = base_url or settings.DEEPSEEK_API_URL.rsplit("/v1", 1)[0] + "/v1"
        self.temperature = temperature if temperature is not None else settings.AI_TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else settings.AI_MAX_TOKENS
        self.max_retries = max_retries
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        """懒加载 OpenAI 客户端实例"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=self.max_retries,
            )
        return self._client

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIResponse:
        """执行 AI 补全调用

        Args:
            prompt: 用户提示文本
            system: 系统提示文本
            schema: JSON Schema 约束输出格式
            temperature: 生成温度（覆盖默认值）
            max_tokens: 最大输出 Token 数（覆盖默认值）
            metadata: 元数据（step_name, run_id 等）

        Returns:
            AIResponse 实例

        Raises:
            AIServiceError: AI 调用失败
        """
        from app.utils.ai_client_core import AIServiceError, _detect_ai_error

        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # 如果有 schema，在 system prompt 中追加约束
        system_suffix = ""
        if schema:
            system_suffix = (
                f"\n\nYou MUST respond with valid JSON matching this schema:\n"
                f"```json\n{json.dumps(schema, indent=2)}\n```"
            )
            if messages:
                messages[0]["content"] += system_suffix
            else:
                messages.append({"role": "system", "content": system_suffix.strip()})

        messages.append({"role": "user", "content": prompt})

        _temperature = temperature if temperature is not None else self.temperature
        _max_tokens = max_tokens if max_tokens is not None else self.max_tokens

        start = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=_temperature,
                max_tokens=_max_tokens,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            content = response.choices[0].message.content or ""
            model_version = response.model or self.model

            # Token 用量
            usage_data = response.usage
            prompt_tokens = usage_data.prompt_tokens if usage_data else 0
            completion_tokens = usage_data.completion_tokens if usage_data else 0
            total_cost_usd = (
                prompt_tokens / 1000 * _COST_PER_1K_PROMPT
                + completion_tokens / 1000 * _COST_PER_1K_COMPLETION
            )
            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost_usd=round(total_cost_usd, 6),
            )

            # 尝试解析 JSON
            parsed = None
            if schema:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning("AI response is not valid JSON despite schema constraint")

            ai_response = AIResponse(
                content=content,
                parsed=parsed,
                usage=usage,
                model_version=model_version,
                latency_ms=latency_ms,
                raw_response=response,
            )

            # 记录调用日志
            self._record_call(ai_response, metadata)

            return ai_response

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"OpenAI call failed: {e}")

            # 记录失败日志
            self._record_failure(str(e), metadata, latency_ms)

            if isinstance(e, AIServiceError):
                raise
            raise _detect_ai_error(e) from e

    def _record_call(
        self,
        response: AIResponse,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """记录成功的 AI 调用日志

        从 metadata 提取审计增强字段（generation_batch_id, scenario_type 等）
        一并写入 AICallLog。
        """
        try:
            from app.ai.call_log import record_call
            db = metadata.get("db") if metadata else None
            record_call(
                db,
                model=response.model_version,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                cost_usd=response.usage.total_cost_usd,
                latency_ms=response.latency_ms,
                step_name=metadata.get("step_name") if metadata else None,
                run_id=metadata.get("run_id") if metadata else None,
                generation_batch_id=metadata.get("generation_batch_id") if metadata else None,
                scenario_type=metadata.get("scenario_type") if metadata else None,
                generation_strategy=metadata.get("generation_strategy") if metadata else None,
                prompt_key=metadata.get("prompt_key") if metadata else None,
                prompt_version=metadata.get("prompt_version") if metadata else None,
                prompt_hash=metadata.get("prompt_hash") if metadata else None,
            )
        except Exception as log_err:
            logger.warning(f"Failed to record AI call log: {log_err}")

    def _record_failure(
        self,
        error_msg: str,
        metadata: Optional[Dict[str, Any]],
        latency_ms: int,
    ) -> None:
        """记录失败的 AI 调用日志

        从 metadata 提取审计增强字段及 error_code，一并写入 AICallLog。
        """
        try:
            from app.ai.call_log import record_call
            db = metadata.get("db") if metadata else None
            record_call(
                db,
                model=self.model,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                step_name=metadata.get("step_name") if metadata else None,
                run_id=metadata.get("run_id") if metadata else None,
                status="failed",
                error_message=error_msg[:500] if error_msg else None,
                generation_batch_id=metadata.get("generation_batch_id") if metadata else None,
                scenario_type=metadata.get("scenario_type") if metadata else None,
                generation_strategy=metadata.get("generation_strategy") if metadata else None,
                prompt_key=metadata.get("prompt_key") if metadata else None,
                prompt_version=metadata.get("prompt_version") if metadata else None,
                prompt_hash=metadata.get("prompt_hash") if metadata else None,
                error_code=metadata.get("error_code") if metadata else None,
            )
        except Exception as log_err:
            logger.warning(f"Failed to record AI failure log: {log_err}")
