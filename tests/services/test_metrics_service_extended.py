"""metrics_service 扩展测试 — sync record_* + async query_* 混合。

迁移说明:
    record_metric / record_metrics 保持 sync（fire-and-forget，使用独立 Session）。
    query_metrics / get_metric_timeseries / get_dashboard_summary 已迁至 async，
    对应测试改为 async def + async_db fixture。_build_filters / _get_dialect_name
    保持 sync 纯函数，对应测试不变。
"""
import pytest
from datetime import datetime

from app.services.metrics_service import (
    record_metric,
    record_metrics,
    query_metrics,
    get_metric_timeseries,
    get_dashboard_summary,
    _build_filters,
    _get_dialect_name,
)
from app.models.pipeline_metric import PipelineMetric, VALID_METRIC_NAMES, FMEA_METRICS


class TestRecordMetric:
    """record_metric sync 测试（使用独立 Session，fire-and-forget）。"""

    def test_invalid_metric_name_raises(self):
        with pytest.raises(ValueError, match="Invalid metric name"):
            record_metric("invalid_metric_name")

    def test_record_valid_metric(self, db):
        result = record_metric(
            "low_confidence_pause",
            value=1.0,
            project_id=1,
        )
        assert result is not None
        assert result.metric_name == "low_confidence_pause"

    def test_record_metric_with_all_fields(self, db):
        result = record_metric(
            "json_validation_failure",
            value=2.5,
            project_id=1,
            iteration_id=1,
            run_id=1,
            step_name="case_generation",
            detail={"key": "value"},
        )
        assert result is not None
        assert result.value == 2.5


class TestRecordMetrics:
    def test_batch_record(self, db):
        metrics = [
            {"metric_name": "low_confidence_pause", "value": 1.0, "project_id": 1},
            {"metric_name": "json_validation_failure", "value": 3.0, "project_id": 1},
        ]
        results = record_metrics(metrics)
        assert len(results) == 2

    def test_skip_invalid_metric_name(self, db):
        metrics = [
            {"metric_name": "invalid_name", "value": 1.0},
            {"metric_name": "low_confidence_pause", "value": 1.0},
        ]
        results = record_metrics(metrics)
        assert len(results) == 1


class TestQueryMetrics:
    """query_metrics async 测试。"""

    async def test_query_returns_list(self, async_db):
        result = await query_metrics(async_db)
        assert isinstance(result, list)

    async def test_query_with_filters(self, async_db):
        result = await query_metrics(async_db, metric_name="low_confidence_pause")
        assert isinstance(result, list)

    async def test_query_by_project(self, async_db):
        result = await query_metrics(async_db, project_id=99999)
        assert isinstance(result, list)
        assert len(result) == 0


class TestBuildFilters:
    def test_empty_filters(self):
        filters = _build_filters()
        assert filters == []

    def test_all_filters(self):
        now = datetime.now()
        filters = _build_filters(
            metric_name="low_confidence_pause",
            project_id=1,
            iteration_id=1,
            run_id=1,
            since=now,
            until=now,
        )
        assert len(filters) == 6


class TestGetDialectName:
    def test_returns_string(self, db):
        name = _get_dialect_name(db)
        assert isinstance(name, str)


class TestGetMetricTimeseries:
    """get_metric_timeseries async 测试。"""

    async def test_returns_list(self, async_db):
        result = await get_metric_timeseries(async_db, "low_confidence_pause")
        assert isinstance(result, list)

    async def test_hour_interval(self, async_db):
        result = await get_metric_timeseries(async_db, "low_confidence_pause", interval="hour")
        assert isinstance(result, list)


class TestGetDashboardSummary:
    """get_dashboard_summary async 测试。"""

    async def test_summary_structure(self, async_db):
        result = await get_dashboard_summary(async_db)
        assert "metrics" in result
        assert "total_metric_types" in result
        assert "active_metric_types" in result


class TestFmeaMetrics:
    def test_contains_expected_names(self):
        assert isinstance(FMEA_METRICS, dict)
        assert len(FMEA_METRICS) > 0
        assert "low_confidence_pause" in VALID_METRIC_NAMES
        assert "json_validation_failure" in VALID_METRIC_NAMES
