"""Agent Prometheus 指标模块。

定义 Agent 架构的 Counter/Histogram/Gauge 指标，提供统一埋点入口。
所有指标注册到 prometheus_client 默认 REGISTRY，由
prometheus-fastapi-instrumentator 暴露的 /metrics 端点采集。

指标概览：
    Counter:
        - agent_sessions_total{agent_type, status}
        - agent_iterations_total{agent_type}
        - agent_tool_calls_total{tool_name, status}
        - agent_loops_detected_total{agent_type}
        - agent_approvals_total{action}
        - agent_circuit_breaker_state{agent_type, state}
    Histogram:
        - agent_session_duration_seconds{agent_type}
        - agent_iteration_duration_seconds{agent_type}
        - agent_token_cost{agent_type}
    Gauge:
        - agent_active_sessions
        - agent_daily_token_consumed{agent_type}

设计原则：
    - 所有埋点方法 swallow 异常（loguru.warning），不阻断主流程
    - AgentMetrics 单例通过 get_metrics() 获取
    - 指标对象模块级定义，避免重复注册
"""
from __future__ import annotations

from typing import Optional

from loguru import logger
from prometheus_client import Counter, Gauge, Histogram

# ── Counter 指标 ──
AGENT_SESSIONS_TOTAL = Counter(
    "agent_sessions_total",
    "Total agent sessions by type and final status",
    labelnames=("agent_type", "status"),
)
AGENT_ITERATIONS_TOTAL = Counter(
    "agent_iterations_total",
    "Total agent iterations by type",
    labelnames=("agent_type",),
)
AGENT_TOOL_CALLS_TOTAL = Counter(
    "agent_tool_calls_total",
    "Total agent tool calls by tool name and status",
    labelnames=("tool_name", "status"),
)
AGENT_LOOPS_DETECTED_TOTAL = Counter(
    "agent_loops_detected_total",
    "Total agent loop detections by type",
    labelnames=("agent_type",),
)
AGENT_APPROVALS_TOTAL = Counter(
    "agent_approvals_total",
    "Total HITL approvals/rejections",
    labelnames=("action",),
)
AGENT_CIRCUIT_BREAKER_STATE = Counter(
    "agent_circuit_breaker_state",
    "Circuit breaker state transitions by agent type",
    labelnames=("agent_type", "state"),
)

# ── Histogram 指标 ──
AGENT_SESSION_DURATION = Histogram(
    "agent_session_duration_seconds",
    "Agent session duration in seconds",
    labelnames=("agent_type",),
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
)
AGENT_ITERATION_DURATION = Histogram(
    "agent_iteration_duration_seconds",
    "Agent iteration duration in seconds",
    labelnames=("agent_type",),
    buckets=(0.2, 0.5, 1, 2, 5, 10, 30, 60),
)
AGENT_TOKEN_COST = Histogram(
    "agent_token_cost",
    "Agent session total token cost distribution",
    labelnames=("agent_type",),
    buckets=(100, 500, 1000, 2000, 5000, 10000, 50000, 200000),
)

# ── Gauge 指标 ──
AGENT_ACTIVE_SESSIONS = Gauge(
    "agent_active_sessions",
    "Current active agent sessions",
)
AGENT_DAILY_TOKEN_CONSUMED = Gauge(
    "agent_daily_token_consumed",
    "Daily token consumed by agent type",
    labelnames=("agent_type",),
)


class AgentMetrics:
    """Agent 指标埋点入口。

    所有方法均 swallow 异常（仅 loguru.warning），保证主流程不受
    监控埋点故障影响。运行时通过 get_metrics() 获取全局单例。
    """

    def record_session_start(self, agent_type: str) -> None:
        """会话开始时调用：active_sessions +1。"""
        try:
            AGENT_ACTIVE_SESSIONS.inc()
        except Exception as e:
            logger.warning(f"metrics record_session_start failed: {e}")

    def record_session_end(
        self, agent_type: str, status: str, duration_seconds: float, token_cost: int,
    ) -> None:
        """会话结束时调用：sessions_total{status}+1 / active_sessions-1 / 时长与 token 观察。"""
        try:
            AGENT_SESSIONS_TOTAL.labels(agent_type=agent_type, status=status).inc()
            AGENT_ACTIVE_SESSIONS.dec()
            AGENT_SESSION_DURATION.labels(agent_type=agent_type).observe(duration_seconds)
            AGENT_TOKEN_COST.labels(agent_type=agent_type).observe(token_cost)
        except Exception as e:
            logger.warning(f"metrics record_session_end failed: {e}")

    def record_iteration(self, agent_type: str, duration_seconds: float) -> None:
        """单轮迭代结束时调用：iterations_total+1 / 时长观察。"""
        try:
            AGENT_ITERATIONS_TOTAL.labels(agent_type=agent_type).inc()
            AGENT_ITERATION_DURATION.labels(agent_type=agent_type).observe(duration_seconds)
        except Exception as e:
            logger.warning(f"metrics record_iteration failed: {e}")

    def record_tool_call(self, tool_name: str, success: bool) -> None:
        """工具调用结束时调用：tool_calls_total{status}+1。"""
        try:
            status = "success" if success else "failure"
            AGENT_TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status=status).inc()
        except Exception as e:
            logger.warning(f"metrics record_tool_call failed: {e}")

    def record_loop_detected(self, agent_type: str) -> None:
        """循环检测触发时调用：loops_detected_total+1。"""
        try:
            AGENT_LOOPS_DETECTED_TOTAL.labels(agent_type=agent_type).inc()
        except Exception as e:
            logger.warning(f"metrics record_loop_detected failed: {e}")

    def record_approval(self, action: str) -> None:
        """HITL 审批时调用：approvals_total{action}+1（approve/reject）。"""
        try:
            AGENT_APPROVALS_TOTAL.labels(action=action).inc()
        except Exception as e:
            logger.warning(f"metrics record_approval failed: {e}")

    def record_circuit_breaker_state(self, agent_type: str, state: str) -> None:
        """熔断器状态转换时调用：state=closed/open/half_open。"""
        try:
            AGENT_CIRCUIT_BREAKER_STATE.labels(agent_type=agent_type, state=state).inc()
        except Exception as e:
            logger.warning(f"metrics record_circuit_breaker_state failed: {e}")

    def set_daily_token_consumed(self, agent_type: str, value: int) -> None:
        """更新当日累计 token 消耗 Gauge。"""
        try:
            AGENT_DAILY_TOKEN_CONSUMED.labels(agent_type=agent_type).set(value)
        except Exception as e:
            logger.warning(f"metrics set_daily_token_consumed failed: {e}")


# 全局单例
_global_metrics: Optional[AgentMetrics] = None


def get_metrics() -> AgentMetrics:
    """获取全局 AgentMetrics 单例。"""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = AgentMetrics()
    return _global_metrics


__all__ = ["AgentMetrics", "get_metrics"]
