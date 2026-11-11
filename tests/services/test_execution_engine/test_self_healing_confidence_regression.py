"""R3-1 自愈置信度回归测试。

锁定三件事：
    1. 权重来自 `settings.AI_SELF_HEALING_CONF_WEIGHT_*`，改配置即可改变评分（不再是硬编码常量）；
    2. 评分对所有输入**单调可预测**，边界值（全命中 / 全缺失）保持稳定；
    3. `get_self_healing_summary()` 暴露三项可查询指标：
       成功率、命中层级分布、平均自愈耗时。
"""
import pytest

from app.core.config import settings
from app.services.test_execution_engine.self_healing_strategy_helpers import (
    compute_confidence,
    explain_confidence,
    get_confidence_weights,
)
from app.services.test_execution_engine.self_healing_utils_mixin import SelfHealingUtilsMixin

COORD_ONLY = {"x": 10, "y": 20, "width": 30, "height": 40}
EMPTY_INFO: dict = {}
ATTRS = {"id": "submit-btn"}


@pytest.fixture(autouse=True)
def _restore_weights():
    """每个用例后恢复默认权重，避免污染其他测试。"""
    original = (
        settings.AI_SELF_HEALING_CONF_WEIGHT_COORD,
        settings.AI_SELF_HEALING_CONF_WEIGHT_ATTR,
        settings.AI_SELF_HEALING_CONF_WEIGHT_MODEL,
    )
    yield
    (
        settings.AI_SELF_HEALING_CONF_WEIGHT_COORD,
        settings.AI_SELF_HEALING_CONF_WEIGHT_ATTR,
        settings.AI_SELF_HEALING_CONF_WEIGHT_MODEL,
    ) = original


def test_default_weights_are_externalized():
    """默认权重从配置读取（0.4 / 0.4 / 0.2）。"""
    assert get_confidence_weights() == (
        pytest.approx(0.4),
        pytest.approx(0.4),
        pytest.approx(0.2),
    )


def test_boundary_full_hit_is_one():
    """全命中 + 模型置信 1.0 → 1.0（上界稳定）。"""
    assert compute_confidence({**COORD_ONLY, "confidence": 1.0}, ATTRS) == pytest.approx(1.0)


def test_boundary_all_missing_is_model_only():
    """全缺失时仅剩模型项：默认模型置信 0.5 × 0.2 = 0.1。"""
    assert compute_confidence(EMPTY_INFO, None) == pytest.approx(0.1)


def test_boundary_zero_model_confidence_is_zero():
    """全缺失且模型置信 0 → 0.0（下界稳定）。"""
    assert compute_confidence({"confidence": 0}, None) == pytest.approx(0.0)


def test_monotonic_by_hit_count():
    """同一权重下，命中层级越多得分越高（单调）。"""
    none_score = compute_confidence({"confidence": 0}, None)
    coord_score = compute_confidence({**COORD_ONLY, "confidence": 0}, None)
    both_score = compute_confidence({**COORD_ONLY, "confidence": 0}, ATTRS)

    assert none_score < coord_score < both_score


def test_monotonic_by_model_confidence():
    """坐标与属性固定时，模型置信度提升 → 总分单调上升。"""
    scores = [
        compute_confidence({**COORD_ONLY, "confidence": conf}, ATTRS)
        for conf in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores == sorted(scores)
    assert scores[-1] == pytest.approx(1.0)


def test_weights_come_from_settings(monkeypatch):
    """修改配置权重后评分随之变化，证明不再硬编码。"""
    baseline = compute_confidence({**COORD_ONLY, "confidence": 0.5}, ATTRS)

    monkeypatch.setattr(settings, "AI_SELF_HEALING_CONF_WEIGHT_COORD", 0.6)
    monkeypatch.setattr(settings, "AI_SELF_HEALING_CONF_WEIGHT_ATTR", 0.3)
    monkeypatch.setattr(settings, "AI_SELF_HEALING_CONF_WEIGHT_MODEL", 0.1)

    adjusted = compute_confidence({**COORD_ONLY, "confidence": 0.5}, ATTRS)

    assert baseline == pytest.approx(0.9)      # 0.4 + 0.4 + 0.2*0.5
    assert adjusted == pytest.approx(0.95)     # 0.6 + 0.3 + 0.1*0.5
    assert adjusted > baseline


def test_invalid_weights_fall_back_to_defaults(monkeypatch):
    """负权重属非法配置，回落到模块默认值而非算出负分。"""
    monkeypatch.setattr(settings, "AI_SELF_HEALING_CONF_WEIGHT_COORD", -1.0)
    monkeypatch.setattr(settings, "AI_SELF_HEALING_CONF_WEIGHT_ATTR", 0.4)
    monkeypatch.setattr(settings, "AI_SELF_HEALING_CONF_WEIGHT_MODEL", 0.2)

    assert get_confidence_weights() == (
        pytest.approx(0.4),
        pytest.approx(0.4),
        pytest.approx(0.2),
    )


def test_explain_confidence_reports_hits():
    """explain_confidence 返回命中层级，供埋点使用。"""
    detail = explain_confidence({**COORD_ONLY, "confidence": 1.0}, ATTRS)

    assert detail["hits"] == {"coordinate": True, "attribute": True, "model": True}
    assert detail["confidence"] == pytest.approx(1.0)

    detail = explain_confidence(EMPTY_INFO, None)
    assert detail["hits"] == {"coordinate": False, "attribute": False, "model": True}


class _SummaryHost(SelfHealingUtilsMixin):
    """最小宿主：只挂载 summary 所需的实例字段。"""

    def __init__(self, attempts: int, successes: int, layer_hits: dict, duration: float):
        self._self_healing_attempts = attempts
        self._self_healing_successes = successes
        self._self_healing_layer_hits = dict(layer_hits)
        self._self_healing_total_duration = duration


def test_summary_exposes_three_metrics():
    """摘要必须含：成功率、层级分布、平均耗时。"""
    host = _SummaryHost(
        attempts=4,
        successes=3,
        layer_hits={"coordinate": 3, "attribute": 1, "model": 4},
        duration=6.0,
    )

    summary = host.get_self_healing_summary()

    assert summary["healing_success_rate"] == pytest.approx(0.75)
    assert summary["self_healing_success_rate"] == pytest.approx(0.75)
    assert summary["healing_layer_hit_counts"] == {"coordinate": 3, "attribute": 1, "model": 4}
    assert summary["healing_layer_hit_distribution"] == {
        "coordinate": pytest.approx(0.375),
        "attribute": pytest.approx(0.125),
        "model": pytest.approx(0.5),
    }
    assert summary["avg_healing_duration_seconds"] == pytest.approx(1.5)


def test_summary_empty_buckets_are_zero():
    """零尝试时所有派生指标为 0，不抛 ZeroDivisionError。"""
    host = _SummaryHost(attempts=0, successes=0, layer_hits={}, duration=0.0)

    summary = host.get_self_healing_summary()

    assert summary["healing_success_rate"] == 0.0
    assert summary["avg_healing_duration_seconds"] == 0.0
    assert summary["healing_layer_hit_distribution"] == {
        "coordinate": 0.0, "attribute": 0.0, "model": 0.0,
    }


def test_record_healing_confidence_accumulates():
    """层级计数按「命中即 +1」累计，非互斥。"""
    host = _SummaryHost(attempts=1, successes=1, layer_hits={}, duration=0.0)

    host._record_healing_confidence(
        {"confidence": 0.9, "hits": {"coordinate": True, "attribute": True, "model": True}}
    )
    host._record_healing_confidence(
        {"confidence": 0.1, "hits": {"coordinate": False, "attribute": False, "model": True}}
    )

    assert host._self_healing_layer_hits == {"coordinate": 1, "attribute": 1, "model": 2}
