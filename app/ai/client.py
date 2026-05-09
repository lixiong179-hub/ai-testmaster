"""
AI Client 抽象接口模块

本模块定义了 Pipeline 所需的统一 AI 调用抽象：
    - AIClient Protocol : 所有 AI 实现必须遵循的接口
    - AIResponse        : AI 响应数据类（content, parsed, usage, model_version, latency_ms, raw_response）
    - TokenUsage        : Token 用量数据类（prompt_tokens, completion_tokens, total_cost_usd）

设计原则：
    - Protocol 而非 ABC：允许运行时 duck-typing，不强制继承
    - metadata 参数传递 step_name/run_id，供 call_log 记录
    - schema 参数支持 JSON Schema 约束输出格式（structured output）

依赖关系：
    - typing.Protocol : 接口定义
    - dataclasses     : 数据类
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@dataclass
class TokenUsage:
    """Token 用量统计

    Attributes:
        prompt_tokens: 输入 Token 数量
        completion_tokens: 输出 Token 数量
        total_cost_usd: 本次调用总成本（美元）
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0


@dataclass
class AIResponse:
    """AI 响应数据类

    Attributes:
        content: 原始文本响应
        parsed: 解析后的结构化数据（如 JSON 对象），可选
        usage: Token 用量统计
        model_version: 实际使用的模型标识（如 "deepseek-v4-flash"）
        latency_ms: 调用耗时（毫秒）
        raw_response: 原始 API 响应对象，可选（调试用）
        degraded: 是否由 fallback 模型生成
    """
    content: str = ""
    parsed: Optional[Dict[str, Any]] = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    model_version: str = ""
    latency_ms: int = 0
    raw_response: Any = None
    degraded: bool = False


@runtime_checkable
class AIClient(Protocol):
    """AI 调用抽象接口

    所有 Step 必须通过此接口调用模型，禁止直接调用模型 API。
    实现类需提供 complete 方法。

    Methods:
        complete: 执行 AI 补全调用
    """

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
            system: 系统提示文本（可选）
            schema: JSON Schema 约束输出格式（可选，structured output）
            temperature: 生成温度（可选，覆盖默认值）
            max_tokens: 最大输出 Token 数（可选，覆盖默认值）
            metadata: 元数据（可选，如 step_name, run_id，供 call_log 记录）

        Returns:
            AIResponse 实例
        """
        ...
