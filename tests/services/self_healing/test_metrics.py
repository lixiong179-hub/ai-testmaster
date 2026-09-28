"""Prometheus 指标埋点单元测试。

覆盖：
    - record_attempt：SELF_HEAL_ATTEMPTS 计数递增
    - record_success：SELF_HEAL_SUCCESS + SELF_HEAL_TOKEN_COST 递增
    - record_failure：SELF_HEAL_FAILURE + SELF_HEAL_FAILURE_TYPE{type} 递增
    - 标签正确性：failure_type 标签值匹配

被测：app/services/self_healing/metrics.py
注意：prometheus_client 默认 REGISTRY 全局，测试间通过 .get_sample_value()
读取当前累计值并断言增量（不重置 REGISTRY，避免与并行测试冲突）。
"""
import pytest
from prometheus_client import REGISTRY

from app.services.self_healing.metrics import (
    SELF_HEAL_ATTEMPTS,
    SELF_HEAL_DURATION,
    SELF_HEAL_FAILURE,
    SELF_HEAL_FAILURE_TYPE,
    SELF_HEAL_SUCCESS,
    SELF_HEAL_TOKEN_COST,
    record_attempt,
    record_failure,
    record_success,
)


def _get_counter_value(metric) -> float:
    """读取 Counter 当前累计值（兼容无 label 与有 label 两种情况）。

    Counter 的 .collect() 返回一个 Sample，其 .value 即累计值。
    """
    samples = list(metric.collect())
    if not samples:
        return 0.0
    # Counter 通常只有一个 sample（不含 label 时 samples[0].samples[0].value）
    sample = samples[0].samples[0]
    return sample.value


def _get_labeled_counter_value(metric, label_name: str, label_value: str) -> float:
    """读取带 label 的 Counter 指定 label 值的累计值。"""
    samples = list(metric.collect())
    if not samples:
        return 0.0
    for sample in samples:
        for s in sample.samples:
            if s.labels.get(label_name) == label_value:
                return s.value
    return 0.0


class TestRecordAttempt:
    """record_attempt 自愈尝试计数。"""

    def test_record_attempt_increments_counter(self):
        """record_attempt 使 SELF_HEAL_ATTEMPTS 计数递增 1。"""
        before = _get_counter_value(SELF_HEAL_ATTEMPTS)
        record_attempt()
        after = _get_counter_value(SELF_HEAL_ATTEMPTS)
        assert after == before + 1

    def test_record_attempt_multiple_increments(self):
        """多次调用 record_attempt 累计递增。"""
        before = _get_counter_value(SELF_HEAL_ATTEMPTS)
        for _ in range(5):
            record_attempt()
        after = _get_counter_value(SELF_HEAL_ATTEMPTS)
        assert after == before + 5


class TestRecordSuccess:
    """record_success 自愈成功计数与 Token 消耗。"""

    def test_record_success_increments_success_counter(self):
        """record_success 使 SELF_HEAL_SUCCESS 递增 1。"""
        before = _get_counter_value(SELF_HEAL_SUCCESS)
        record_success(token_cost=500, duration=1.5)
        after = _get_counter_value(SELF_HEAL_SUCCESS)
        assert after == before + 1

    def test_record_success_accumulates_token_cost(self):
        """record_success 累计 token_cost 到 SELF_HEAL_TOKEN_COST。"""
        before = _get_counter_value(SELF_HEAL_TOKEN_COST)
        record_success(token_cost=500, duration=1.5)
        record_success(token_cost=300, duration=2.0)
        after = _get_counter_value(SELF_HEAL_TOKEN_COST)
        assert after == before + 800

    def test_record_success_zero_token_cost(self):
        """token_cost=0 时 SELF_HEAL_TOKEN_COST 不变。"""
        before = _get_counter_value(SELF_HEAL_TOKEN_COST)
        record_success(token_cost=0, duration=1.0)
        after = _get_counter_value(SELF_HEAL_TOKEN_COST)
        assert after == before

    def test_record_success_observes_duration_histogram(self):
        """record_success 将 duration 观察到 SELF_HEAL_DURATION 直方图。

        直方图的 _sum 样本累计所有观察值的和。
        """
        # 直方图通过 _sum 样本累计观察值
        before_sum = 0.0
        for sample in SELF_HEAL_DURATION.collect():
            for s in sample.samples:
                if s.name == "self_heal_duration_seconds_sum":
                    before_sum = s.value
                    break
        record_success(token_cost=100, duration=2.5)
        after_sum = 0.0
        for sample in SELF_HEAL_DURATION.collect():
            for s in sample.samples:
                if s.name == "self_heal_duration_seconds_sum":
                    after_sum = s.value
                    break
        assert after_sum == before_sum + 2.5


class TestRecordFailure:
    """record_failure 自愈失败计数与按类型统计。"""

    def test_record_failure_increments_failure_counter(self):
        """record_failure 使 SELF_HEAL_FAILURE 递增 1。"""
        before = _get_counter_value(SELF_HEAL_FAILURE)
        record_failure(failure_type="element_gone", duration=1.0)
        after = _get_counter_value(SELF_HEAL_FAILURE)
        assert after == before + 1

    def test_record_failure_type_label_element_gone(self):
        """failure_type=element_gone 标签正确递增。"""
        before = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "element_gone"
        )
        record_failure(failure_type="element_gone", duration=1.0)
        after = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "element_gone"
        )
        assert after == before + 1

    def test_record_failure_type_label_dom_changed(self):
        """failure_type=dom_changed 标签正确递增。"""
        before = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "dom_changed"
        )
        record_failure(failure_type="dom_changed", duration=1.0)
        after = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "dom_changed"
        )
        assert after == before + 1

    def test_record_failure_type_label_load_delay(self):
        """failure_type=load_delay 标签正确递增。"""
        before = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "load_delay"
        )
        record_failure(failure_type="load_delay", duration=1.0)
        after = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "load_delay"
        )
        assert after == before + 1

    def test_record_failure_type_label_env_noise(self):
        """failure_type=env_noise 标签正确递增。"""
        before = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "env_noise"
        )
        record_failure(failure_type="env_noise", duration=1.0)
        after = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "env_noise"
        )
        assert after == before + 1

    def test_record_failure_type_labels_isolated(self):
        """不同 failure_type 标签互不影响。"""
        before_gone = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "element_gone"
        )
        before_noise = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "env_noise"
        )
        record_failure(failure_type="element_gone", duration=1.0)
        after_gone = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "element_gone"
        )
        after_noise = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "env_noise"
        )
        assert after_gone == before_gone + 1
        assert after_noise == before_noise  # env_noise 不受影响

    def test_record_failure_observes_duration_histogram(self):
        """record_failure 将 duration 观察到 SELF_HEAL_DURATION 直方图。"""
        before_sum = 0.0
        for sample in SELF_HEAL_DURATION.collect():
            for s in sample.samples:
                if s.name == "self_heal_duration_seconds_sum":
                    before_sum = s.value
                    break
        record_failure(failure_type="element_gone", duration=3.5)
        after_sum = 0.0
        for sample in SELF_HEAL_DURATION.collect():
            for s in sample.samples:
                if s.name == "self_heal_duration_seconds_sum":
                    after_sum = s.value
                    break
        assert after_sum == before_sum + 3.5

    def test_record_failure_multiple_types_accumulate(self):
        """多次不同类型失败累计，每个标签独立计数。"""
        before_gone = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "element_gone"
        )
        before_changed = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "dom_changed"
        )
        for _ in range(3):
            record_failure(failure_type="element_gone", duration=1.0)
        for _ in range(2):
            record_failure(failure_type="dom_changed", duration=1.0)
        after_gone = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "element_gone"
        )
        after_changed = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "dom_changed"
        )
        assert after_gone == before_gone + 3
        assert after_changed == before_changed + 2


class TestMetricsRegistration:
    """指标注册与命名验证。"""

    def test_self_heal_attempts_registered(self):
        """SELF_HEAL_ATTEMPTS 在 REGISTRY 中可查询。"""
        value = REGISTRY.get_sample_value("self_heal_attempts_total")
        assert value is not None
        assert isinstance(value, float)

    def test_self_heal_success_registered(self):
        """SELF_HEAL_SUCCESS 在 REGISTRY 中可查询。"""
        value = REGISTRY.get_sample_value("self_heal_success_total")
        assert value is not None

    def test_self_heal_failure_registered(self):
        """SELF_HEAL_FAILURE 在 REGISTRY 中可查询。"""
        value = REGISTRY.get_sample_value("self_heal_failure_total")
        assert value is not None

    def test_self_heal_token_cost_registered(self):
        """SELF_HEAL_TOKEN_COST 在 REGISTRY 中可查询。"""
        value = REGISTRY.get_sample_value("self_heal_token_cost_total")
        assert value is not None

    def test_self_heal_duration_histogram_registered(self):
        """SELF_HEAL_DURATION 直方图在 REGISTRY 中可查询。"""
        # 直方图有 _sum / _count / _bucket 多个样本
        sum_value = REGISTRY.get_sample_value("self_heal_duration_seconds_sum")
        assert sum_value is not None
        count_value = REGISTRY.get_sample_value("self_heal_duration_seconds_count")
        assert count_value is not None

    def test_self_heal_failure_type_labels_registered(self):
        """SELF_HEAL_FAILURE_TYPE 带 label 的样本在 REGISTRY 中可查询。"""
        # 先记录一次以保证 label 存在
        record_failure(failure_type="element_gone", duration=1.0)
        value = REGISTRY.get_sample_value(
            "self_heal_failure_type_total",
            labels={"type": "element_gone"},
        )
        assert value is not None


class TestEndToEndMetricsFlow:
    """端到端：尝试 → 成功/失败 完整埋点流程。"""

    def test_attempt_then_success_flow(self):
        """尝试 → 成功流程的指标递增。"""
        before_attempts = _get_counter_value(SELF_HEAL_ATTEMPTS)
        before_success = _get_counter_value(SELF_HEAL_SUCCESS)
        before_token = _get_counter_value(SELF_HEAL_TOKEN_COST)

        record_attempt()
        record_success(token_cost=1200, duration=2.5)

        after_attempts = _get_counter_value(SELF_HEAL_ATTEMPTS)
        after_success = _get_counter_value(SELF_HEAL_SUCCESS)
        after_token = _get_counter_value(SELF_HEAL_TOKEN_COST)

        assert after_attempts == before_attempts + 1
        assert after_success == before_success + 1
        assert after_token == before_token + 1200

    def test_attempt_then_failure_flow(self):
        """尝试 → 失败流程的指标递增。"""
        before_attempts = _get_counter_value(SELF_HEAL_ATTEMPTS)
        before_failure = _get_counter_value(SELF_HEAL_FAILURE)
        before_failure_type = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "load_delay"
        )

        record_attempt()
        record_failure(failure_type="load_delay", duration=1.8)

        after_attempts = _get_counter_value(SELF_HEAL_ATTEMPTS)
        after_failure = _get_counter_value(SELF_HEAL_FAILURE)
        after_failure_type = _get_labeled_counter_value(
            SELF_HEAL_FAILURE_TYPE, "type", "load_delay"
        )

        assert after_attempts == before_attempts + 1
        assert after_failure == before_failure + 1
        assert after_failure_type == before_failure_type + 1

    def test_mixed_success_failure_flow(self):
        """混合成功/失败流程的指标正确递增。"""
        before_attempts = _get_counter_value(SELF_HEAL_ATTEMPTS)
        before_success = _get_counter_value(SELF_HEAL_SUCCESS)
        before_failure = _get_counter_value(SELF_HEAL_FAILURE)

        # 5 次尝试：3 成功 + 2 失败
        for _ in range(3):
            record_attempt()
            record_success(token_cost=100, duration=1.0)
        for _ in range(2):
            record_attempt()
            record_failure(failure_type="env_noise", duration=1.0)

        after_attempts = _get_counter_value(SELF_HEAL_ATTEMPTS)
        after_success = _get_counter_value(SELF_HEAL_SUCCESS)
        after_failure = _get_counter_value(SELF_HEAL_FAILURE)

        assert after_attempts == before_attempts + 5
        assert after_success == before_success + 3
        assert after_failure == before_failure + 2
