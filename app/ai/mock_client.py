"""
Mock AI Client 实现

本模块提供测试用 Mock AI Client，返回预设 JSON，零 AI 调用成本。
用于 Pipeline Step 单测和集成测试。

核心特性：
    - 零成本：TokenUsage 全部为 0
    - 可配置响应：通过 set_response 预设返回内容
    - 自动 JSON 解析：如果 preset 是 dict，自动设置 parsed
    - 调用计数：记录 complete 被调用的次数和参数

依赖关系：
    - app.ai.client : AIResponse, TokenUsage, AIClient
"""
import json
import time
from typing import Any, Dict, List, Optional

from app.ai.client import AIResponse, TokenUsage


class MockAIClient:
    """Mock AI Client 实现

    测试用 Mock，返回预设响应，零 AI 调用成本。

    Attributes:
        default_response: 默认预设响应内容
        call_history: 调用历史记录列表
    """

    def __init__(self, default_response: Any = None) -> None:
        self.default_response = default_response or {"result": "mock"}
        self.call_history: List[Dict[str, Any]] = []
        self._response_map: Dict[str, Any] = {}

    def set_response(self, key: str, response: Any) -> None:
        """按 key 预设响应

        Args:
            key: 匹配键（与 metadata["step_name"] 对应）
            response: 预设响应内容（str 或 dict）
        """
        self._response_map[key] = response

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
        """执行 Mock 补全调用

        根据 metadata["step_name"] 查找预设响应，未找到则使用 default_response。
        dict 类型响应自动序列化为 JSON content 并设置 parsed。

        Args:
            prompt: 用户提示文本（记录但不使用）
            system: 系统提示文本（记录但不使用）
            schema: JSON Schema（记录但不使用）
            temperature: 生成温度（记录但不使用）
            max_tokens: 最大输出 Token 数（记录但不使用）
            metadata: 元数据（用于查找预设响应）

        Returns:
            AIResponse 实例（零成本）
        """
        start = time.monotonic()

        # 查找预设响应
        step_name = metadata.get("step_name") if metadata else None
        response_data = self._response_map.get(step_name, self.default_response) if step_name else self.default_response

        # 构造响应
        if isinstance(response_data, dict):
            content = json.dumps(response_data, ensure_ascii=False)
            parsed = response_data
        else:
            content = str(response_data)
            parsed = None

        latency_ms = max(1, int((time.monotonic() - start) * 1000))

        # 记录调用历史
        self.call_history.append({
            "prompt": prompt,
            "system": system,
            "schema": schema,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "metadata": metadata,
            "response_content": content,
        })

        return AIResponse(
            content=content,
            parsed=parsed,
            usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_cost_usd=0.0),
            model_version="mock-model",
            latency_ms=latency_ms,
            raw_response=None,
            degraded=False,
        )

    @property
    def call_count(self) -> int:
        """complete 被调用的次数"""
        return len(self.call_history)

    def reset(self) -> None:
        """重置调用历史和预设响应"""
        self.call_history.clear()
        self._response_map.clear()
