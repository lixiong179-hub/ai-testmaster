"""
Fallback AI Client 实现

本模块实现主备切换逻辑：
    - 主模型失败 3 次后自动切换到备用模型
    - 备用模型返回的 AIResponse 标记 degraded=True
    - 切换后后续调用直接使用备用模型（不自动回切）

依赖关系：
    - app.ai.client : AIClient Protocol, AIResponse, TokenUsage
    - app.utils.ai_client_core : AIServiceError
"""
from typing import Any, Dict, Optional

from loguru import logger

from app.ai.client import AIResponse


class FallbackAIClient:
    """主备切换 AI Client 实现

    主模型失败达到阈值后自动切备用模型，备用模型响应标记 degraded=True。

    Attributes:
        primary: 主 AI Client
        fallback: 备用 AI Client
        max_failures: 触发切换的连续失败次数
        failure_count: 当前连续失败计数
        switched: 是否已切换到备用模型
    """

    def __init__(
        self,
        primary: Any,
        fallback: Any,
        *,
        max_failures: int = 3,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.max_failures = max_failures
        self.failure_count = 0
        self.switched = False

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
        """执行 AI 补全调用（含主备切换逻辑）

        1. 如果已切换到备用模型，直接调用备用
        2. 否则尝试主模型，成功则重置失败计数
        3. 主模型失败则累加计数，达到阈值后切换备用

        Args:
            prompt: 用户提示文本
            system: 系统提示文本
            schema: JSON Schema 约束
            temperature: 生成温度
            max_tokens: 最大输出 Token 数
            metadata: 元数据

        Returns:
            AIResponse 实例（备用模型响应标记 degraded=True）

        Raises:
            AIServiceError: 主备模型均失败时抛出
        """
        # 已切换 → 直接用备用
        if self.switched:
            return self._call_fallback(
                prompt, system=system, schema=schema,
                temperature=temperature, max_tokens=max_tokens,
                metadata=metadata,
            )

        # 尝试主模型
        try:
            response = self.primary.complete(
                prompt, system=system, schema=schema,
                temperature=temperature, max_tokens=max_tokens,
                metadata=metadata,
            )
            self.failure_count = 0  # 成功则重置
            return response
        except Exception as e:
            self.failure_count += 1
            logger.warning(
                f"Primary model failed ({self.failure_count}/{self.max_failures}): {e}"
            )

            if self.failure_count >= self.max_failures:
                logger.warning(
                    f"Primary model failed {self.max_failures} times, switching to fallback"
                )
                self.switched = True
                _record_fallback_metric()
                return self._call_fallback(
                    prompt, system=system, schema=schema,
                    temperature=temperature, max_tokens=max_tokens,
                    metadata=metadata,
                )

            # 未达阈值，继续抛出异常让调用方重试
            raise

    def _call_fallback(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIResponse:
        """调用备用模型并标记 degraded"""
        response = self.fallback.complete(
            prompt, system=system, schema=schema,
            temperature=temperature, max_tokens=max_tokens,
            metadata=metadata,
        )
        response.degraded = True
        return response

    def reset(self) -> None:
        """重置切换状态（用于新 Run）"""
        self.failure_count = 0
        self.switched = False


def _record_fallback_metric() -> None:
    """记录 F12 Fallback 模型调用指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        record_metric("fallback_model_used", detail={"trigger": "primary_model_failure"})
    except Exception as e:
        logger.debug(f"记录fallback指标失败(不影响业务): {e}")
