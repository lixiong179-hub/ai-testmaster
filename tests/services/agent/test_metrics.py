"""AgentMetrics 单元测试。

覆盖：
    - record_session_start/end 计数与 Gauge 变化
    - record_iteration 计数与时长观察
    - record_tool_call success/failure 分支
    - record_loop_detected / record_approval / record_circuit_breaker_state
    - set_daily_token_consumed Gauge 设置
    - get_metrics 单例
    - 异常 swallow 不抛出

被测：app/services/agent/metrics.py

注意：prometheus_client 默认 REGISTRY 全局，测试间通过 before/after 增量断言
（不重置 REGISTRY，避免与并行测试冲突）。
"""
from unittest.mock import patch

import app.services.agent.metrics as metrics_module
from app.services.agent.metrics import (
    AGENT_ACTIVE_SESSIONS,
    AGENT_APPROVALS_TOTAL,
    AGENT_CIRCUIT_BREAKER_STATE,
    AGENT_DAILY_TOKEN_CONSUMED,
    AGENT_ITERATIONS_TOTAL,
    AGENT_ITERATION_DURATION,
    AGENT_LOOPS_DETECTED_TOTAL,
    AGENT_SESSIONS_TOTAL,
    AGENT_SESSION_DURATION,
    AGENT_TOKEN_COST,
    AGENT_TOOL_CALLS_TOTAL,
    AgentMetrics,
    get_metrics,
)


def _counter_value(metric, labels=None) -> float:
    """读取 Counter 在指定 labels 下的当前累计值。"""
    for sample in metric.collect():
        for s in sample.samples:
            if labels is None or all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return 0.0


def _gauge_value(metric, labels=None) -> float:
    """读取 Gauge 在指定 labels 下的当前值。"""
    for sample in metric.collect():
        for s in sample.samples:
            if labels is None or all(s.labels.get(k) == v for k, v in labels.items()):
                return s.value
    return 0.0


def _histogram_count(metric, labels=None) -> float:
    """读取 Histogram 在指定 labels 下的观察次数（_count 样本）。"""
    for sample in metric.collect():
        for s in sample.samples:
            if s.name.endswith("_count") and (
                labels is None or all(s.labels.get(k) == v for k, v in labels.items())
            ):
                return s.value
    return 0.0


class TestSessionMetrics:
    """会话指标。"""

    def test_record_session_start_increments_active_sessions(self):
        """record_session_start → AGENT_ACTIVE_SESSIONS 递增。"""
        before = _gauge_value(AGENT_ACTIVE_SESSIONS)
        AgentMetrics().record_session_start("test_start_agent")
        after = _gauge_value(AGENT_ACTIVE_SESSIONS)
        assert after == before + 1

    def test_record_session_end_increments_total_and_observes(self):
        """record_session_end → sessions_total+1 / active-1 / 时长与 token 观察。"""
        labels = {"agent_type": "test_end_agent", "status": "success"}
        before_total = _counter_value(AGENT_SESSIONS_TOTAL, labels)
        before_active = _gauge_value(AGENT_ACTIVE_SESSIONS)
        before_dur = _histogram_count(AGENT_SESSION_DURATION, {"agent_type": "test_end_agent"})
        before_token = _histogram_count(AGENT_TOKEN_COST, {"agent_type": "test_end_agent"})
        AgentMetrics().record_session_end("test_end_agent", "success", 1.5, 1000)
        assert _counter_value(AGENT_SESSIONS_TOTAL, labels) == before_total + 1
        assert _gauge_value(AGENT_ACTIVE_SESSIONS) == before_active - 1
        assert _histogram_count(AGENT_SESSION_DURATION, {"agent_type": "test_end_agent"}) == before_dur + 1
        assert _histogram_count(AGENT_TOKEN_COST, {"agent_type": "test_end_agent"}) == before_token + 1


class TestIterationMetrics:
    """迭代指标。"""

    def test_record_iteration_increments_and_observes(self):
        """record_iteration → iterations_total+1 / 时长观察。"""
        labels = {"agent_type": "test_iter_agent"}
        before_total = _counter_value(AGENT_ITERATIONS_TOTAL, labels)
        before_dur = _histogram_count(AGENT_ITERATION_DURATION, labels)
        AgentMetrics().record_iteration("test_iter_agent", 0.5)
        assert _counter_value(AGENT_ITERATIONS_TOTAL, labels) == before_total + 1
        assert _histogram_count(AGENT_ITERATION_DURATION, labels) == before_dur + 1


class TestToolCallMetrics:
    """工具调用指标。"""

    def test_record_tool_call_success(self):
        """record_tool_call(success=True) → tool_calls_total{status=success}+1。"""
        labels = {"tool_name": "search", "status": "success"}
        before = _counter_value(AGENT_TOOL_CALLS_TOTAL, labels)
        AgentMetrics().record_tool_call("search", True)
        assert _counter_value(AGENT_TOOL_CALLS_TOTAL, labels) == before + 1

    def test_record_tool_call_failure(self):
        """record_tool_call(success=False) → tool_calls_total{status=failure}+1。"""
        labels = {"tool_name": "search", "status": "failure"}
        before = _counter_value(AGENT_TOOL_CALLS_TOTAL, labels)
        AgentMetrics().record_tool_call("search", False)
        assert _counter_value(AGENT_TOOL_CALLS_TOTAL, labels) == before + 1


class TestEventMetrics:
    """事件指标。"""

    def test_record_loop_detected(self):
        """record_loop_detected → loops_detected_total{agent_type}+1。"""
        labels = {"agent_type": "loop_agent"}
        before = _counter_value(AGENT_LOOPS_DETECTED_TOTAL, labels)
        AgentMetrics().record_loop_detected("loop_agent")
        assert _counter_value(AGENT_LOOPS_DETECTED_TOTAL, labels) == before + 1

    def test_record_approval(self):
        """record_approval('approve') → approvals_total{action=approve}+1。"""
        labels = {"action": "approve"}
        before = _counter_value(AGENT_APPROVALS_TOTAL, labels)
        AgentMetrics().record_approval("approve")
        assert _counter_value(AGENT_APPROVALS_TOTAL, labels) == before + 1

    def test_record_circuit_breaker_state(self):
        """record_circuit_breaker_state('open') → cb_state{state=open}+1。"""
        labels = {"agent_type": "cb_agent", "state": "open"}
        before = _counter_value(AGENT_CIRCUIT_BREAKER_STATE, labels)
        AgentMetrics().record_circuit_breaker_state("cb_agent", "open")
        assert _counter_value(AGENT_CIRCUIT_BREAKER_STATE, labels) == before + 1


class TestGaugeMetrics:
    """Gauge 指标。"""

    def test_set_daily_token_consumed(self):
        """set_daily_token_consumed → daily_token_consumed{agent_type} 设置值。"""
        AgentMetrics().set_daily_token_consumed("daily_agent", 12345)
        assert _gauge_value(AGENT_DAILY_TOKEN_CONSUMED, {"agent_type": "daily_agent"}) == 12345


class TestSingleton:
    """单例模式。"""

    def test_get_metrics_singleton(self):
        """get_metrics() 两次调用返回同一实例。"""
        original = metrics_module._global_metrics
        metrics_module._global_metrics = None
        try:
            m1 = get_metrics()
            m2 = get_metrics()
            assert m1 is m2
        finally:
            metrics_module._global_metrics = original


class TestExceptionSwallow:
    """异常吞没。"""

    def test_all_methods_swallow_exceptions(self):
        """所有方法 swallow 异常不抛出（Mock 底层指标抛异常，方法不应抛出）。"""
        m = AgentMetrics()
        with patch.object(metrics_module.AGENT_ACTIVE_SESSIONS, "inc", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_ACTIVE_SESSIONS, "dec", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_SESSIONS_TOTAL, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_SESSION_DURATION, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_TOKEN_COST, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_ITERATIONS_TOTAL, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_ITERATION_DURATION, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_TOOL_CALLS_TOTAL, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_LOOPS_DETECTED_TOTAL, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_APPROVALS_TOTAL, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_CIRCUIT_BREAKER_STATE, "labels", side_effect=RuntimeError), \
             patch.object(metrics_module.AGENT_DAILY_TOKEN_CONSUMED, "labels", side_effect=RuntimeError):
            m.record_session_start("test")
            m.record_session_end("test", "success", 1.0, 100)
            m.record_iteration("test", 1.0)
            m.record_tool_call("tool", True)
            m.record_tool_call("tool", False)
            m.record_loop_detected("test")
            m.record_approval("approve")
            m.record_circuit_breaker_state("test", "open")
            m.set_daily_token_consumed("test", 1000)
