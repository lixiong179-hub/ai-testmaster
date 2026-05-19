import pytest
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
    def test_query_returns_list(self, db):
        result = query_metrics(db)
        assert isinstance(result, list)

    def test_query_with_filters(self, db):
        result = query_metrics(db, metric_name="low_confidence_pause")
        assert isinstance(result, list)

    def test_query_by_project(self, db):
        result = query_metrics(db, project_id=99999)
        assert isinstance(result, list)
        assert len(result) == 0


class TestBuildFilters:
    def test_empty_filters(self):
        filters = _build_filters()
        assert filters == []

    def test_all_filters(self):
        from datetime import datetime
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
    def test_returns_list(self, db):
        result = get_metric_timeseries(db, "low_confidence_pause")
        assert isinstance(result, list)

    def test_hour_interval(self, db):
        result = get_metric_timeseries(db, "low_confidence_pause", interval="hour")
        assert isinstance(result, list)


class TestGetDashboardSummary:
    def test_summary_structure(self, db):
        result = get_dashboard_summary(db)
        assert "metrics" in result
        assert "total_metric_types" in result
        assert "active_metric_types" in result


class TestFmeaMetrics:
    def test_contains_expected_names(self):
        assert isinstance(FMEA_METRICS, dict)
        assert len(FMEA_METRICS) > 0
        assert "low_confidence_pause" in VALID_METRIC_NAMES
        assert "json_validation_failure" in VALID_METRIC_NAMES
