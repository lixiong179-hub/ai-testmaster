"""自愈 Prometheus 指标模块。

定义自愈体系的 Counter/Histogram 指标，并提供统一埋点辅助函数。
所有指标注册到 prometheus_client 默认 REGISTRY，由
prometheus-fastapi-instrumentator 暴露的 /metrics 端点采集。

核心指标：
    - SELF_HEAL_ATTEMPTS     : 自愈尝试总数
    - SELF_HEAL_SUCCESS      : 自愈成功数
    - SELF_HEAL_FAILURE      : 自愈失败数
    - SELF_HEAL_DURATION     : 自愈耗时分布（秒）
    - SELF_HEAL_TOKEN_COST   : Token 消耗总量
    - SELF_HEAL_FAILURE_TYPE : 按失败类型统计的失败数

辅助函数：
    - record_attempt()                       : 记录一次尝试
    - record_success(token_cost, duration)   : 记录成功与耗时
    - record_failure(failure_type, duration) : 记录失败与耗时
"""
from prometheus_client import Counter, Histogram

# 自愈尝试总数
SELF_HEAL_ATTEMPTS = Counter(
    "self_heal_attempts_total", "Total self-healing attempts"
)
# 自愈成功数
SELF_HEAL_SUCCESS = Counter(
    "self_heal_success_total", "Total self-healing successes"
)
# 自愈失败数
SELF_HEAL_FAILURE = Counter(
    "self_heal_failure_total", "Total self-healing failures"
)
# 自愈耗时分布（秒），桶覆盖 0.5s~60s 的典型自愈耗时区间
SELF_HEAL_DURATION = Histogram(
    "self_heal_duration_seconds",
    "Self-healing duration in seconds",
    buckets=(0.5, 1, 2, 5, 8, 15, 30, 60),
)
# Token 消耗总量
SELF_HEAL_TOKEN_COST = Counter(
    "self_heal_token_cost_total", "Total token cost of self-healing"
)
# 按失败类型统计的失败数，label 区分 element_gone/dom_changed/load_delay/env_noise
SELF_HEAL_FAILURE_TYPE = Counter(
    "self_heal_failure_type_total",
    "Self-healing failures by type",
    labelnames=("type",),
)


def record_attempt() -> None:
    """记录一次自愈尝试（递增尝试计数器）。"""
    SELF_HEAL_ATTEMPTS.inc()


def record_success(token_cost: int, duration: float) -> None:
    """记录一次自愈成功：累加成功计数、Token 消耗与耗时分布。

    Args:
        token_cost: 本次自愈消耗的 Token 数。
        duration:   本次自愈耗时（秒）。
    """
    SELF_HEAL_SUCCESS.inc()
    SELF_HEAL_TOKEN_COST.inc(token_cost)
    SELF_HEAL_DURATION.observe(duration)


def record_failure(failure_type: str, duration: float) -> None:
    """记录一次自愈失败：累加失败计数、按类型计数与耗时分布。

    Args:
        failure_type: 失败原因分类（element_gone/dom_changed/load_delay/env_noise）。
        duration:     本次自愈耗时（秒）。
    """
    SELF_HEAL_FAILURE.inc()
    SELF_HEAL_FAILURE_TYPE.labels(type=failure_type).inc()
    SELF_HEAL_DURATION.observe(duration)
