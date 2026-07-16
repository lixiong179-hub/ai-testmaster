"""
OpenAI 兼容 AI Client 异步实现

本模块从 `app.ai.openai_client` 拆分而来，仅包含 `AsyncOpenAIClient`：
    - 使用 AsyncOpenAI SDK 直接异步调用
    - 通过 asyncio.wait_for 强制单次调用超时
    - 复用 OpenAIClient 的 _record_call / _record_failure 日志逻辑（复制实现，
      保持现有行为）

依赖关系：
    - openai.AsyncOpenAI : OpenAI SDK 异步客户端
    - app.core.config.settings : 全局配置
    - app.ai.client : AIResponse, TokenUsage
    - app.ai.openai_client : _COST_PER_1K_PROMPT, _COST_PER_1K_COMPLETION 定价常量
    - app.utils.ai_client_core : AIServiceError, _detect_ai_error
"""
import asyncio
import json
import time
from typing import Any, Dict, Optional

from loguru import logger
from openai import AsyncOpenAI

from app.ai.client import AIResponse, TokenUsage
from app.ai.openai_client import _COST_PER_1K_COMPLETION, _COST_PER_1K_PROMPT
from app.core.config import settings


class AsyncOpenAIClient:
    """OpenAI 兼容 AI Client 异步实现

    性能优化：原 OpenAIClient.complete 是同步方法，调用方需用 asyncio.to_thread
    包装，且无单次调用超时，最坏情况阻塞 worker 75s+。本类使用 AsyncOpenAI
    SDK 直接异步调用，并通过 asyncio.wait_for 强制单次调用超时。

    与 OpenAIClient 共享 _record_call / _record_failure 日志逻辑与配置读取。
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
        self._async_client: Optional[AsyncOpenAI] = None

    @property
    def async_client(self) -> AsyncOpenAI:
        """懒加载 AsyncOpenAI 客户端实例。"""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=self.max_retries,
            )
        return self._async_client

    async def complete_async(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> AIResponse:
        """异步执行 AI 补全调用，含单次调用硬超时。

        Args:
            prompt: 用户提示文本
            system: 系统提示文本
            schema: JSON Schema 约束输出格式
            temperature: 生成温度（覆盖默认值）
            max_tokens: 最大输出 Token 数（覆盖默认值）
            metadata: 元数据（step_name, run_id 等）
            timeout: 单次调用超时秒数，未指定时取 settings.AI_CALL_TIMEOUT_SECONDS

        Returns:
            AIResponse 实例

        Raises:
            AIServiceError: AI 调用失败
            asyncio.TimeoutError: 调用超过 timeout 秒未返回
        """
        from app.utils.ai_client_core import AIServiceError, _detect_ai_error

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})

        # 如果有 schema，在 system prompt 中追加约束
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
        _timeout = timeout if timeout is not None else float(settings.AI_CALL_TIMEOUT_SECONDS)

        start = time.monotonic()
        try:
            # asyncio.wait_for 强制超时，避免长尾请求拖垮 worker
            response = await asyncio.wait_for(
                self.async_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=_temperature,
                    max_tokens=_max_tokens,
                ),
                timeout=_timeout,
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

            # 记录调用日志（复用 OpenAIClient 静态逻辑）
            self._record_call(ai_response, metadata)

            return ai_response

        except asyncio.TimeoutError:
            latency_ms = int((time.monotonic() - start) * 1000)
            error_msg = f"AI call timeout after {_timeout}s"
            logger.error(error_msg)
            self._record_failure(error_msg, metadata, latency_ms)
            raise

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"Async OpenAI call failed: {e}")
            self._record_failure(str(e), metadata, latency_ms)

            if isinstance(e, AIServiceError):
                raise
            raise _detect_ai_error(e) from e

    # 复用 OpenAIClient 的日志记录逻辑（静态化以供两个类共享）
    def _record_call(
        self,
        response: AIResponse,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """记录成功的 AI 调用日志。"""
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
        """记录失败的 AI 调用日志。"""
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
