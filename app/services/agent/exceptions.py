"""Agent 架构异常体系。

设计目的：
    AgentRuntime 多轮循环中可能触发多种异常情况（循环检测、Token 超限、
    工具执行失败、上下文截断、迭代上限触达、熔断器开启），统一异常基类
    便于上层端点分类处理（429/503/500）与审计记录。

异常分类：
    - AgentError: 所有 Agent 异常的基类
    - AgentLoopDetected: 循环检测触发（会话状态 → loop_detected）
    - TokenBudgetExceeded: 单次或日预算超限（会话状态 → token_exhausted）
    - ToolExecutionError: 工具执行失败（会话状态 → failed）
    - ContextTruncated: 上下文超长被截断（不终止会话，仅记录警告）
    - MaxIterationsExceeded: 迭代次数触达上限（会话状态 → failed）
    - CircuitBreakerOpen: 熔断器开启拒绝新会话（HTTP 503）

所有异常携带 agent_type 与可选 session_id，便于审计与日志关联。
"""
from __future__ import annotations

from typing import Optional


class AgentError(Exception):
    """Agent 异常基类。

    Attributes:
        agent_type: 触发异常的 Agent 类型标识。
        session_id: 关联的会话 ID，未创建会话时为 None。
    """

    def __init__(
        self,
        message: str,
        *,
        agent_type: str = "",
        session_id: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.agent_type = agent_type
        self.session_id = session_id


class AgentLoopDetected(AgentError):
    """循环检测触发：最近 N 次工具调用 hash 重复，会话置为 loop_detected。"""


class TokenBudgetExceeded(AgentError):
    """Token 预算超限：单次调用超 AI_AGENT_TOKEN_LIMIT 或日预算耗尽。"""


class ToolExecutionError(AgentError):
    """工具执行失败：服务端工具抛异常或客户端工具回调失败。"""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        agent_type: str = "",
        session_id: Optional[int] = None,
    ) -> None:
        super().__init__(message, agent_type=agent_type, session_id=session_id)
        self.tool_name = tool_name


class ContextTruncated(AgentError):
    """上下文超长被截断：历史消息 + artifacts 超过 LLM 上下文窗口。

    此异常不终止会话，仅记录警告并按策略截断历史。
    """


class MaxIterationsExceeded(AgentError):
    """迭代次数触达上限：超过 AI_AGENT_MAX_ITERATIONS，会话置为 failed。"""


class CircuitBreakerOpen(AgentError):
    """熔断器开启：连续失败超阈值，拒绝新会话创建（HTTP 503）。"""


__all__ = [
    "AgentError",
    "AgentLoopDetected",
    "TokenBudgetExceeded",
    "ToolExecutionError",
    "ContextTruncated",
    "MaxIterationsExceeded",
    "CircuitBreakerOpen",
]
