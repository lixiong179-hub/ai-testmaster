"""M4-T05 FMEA 监控指标服务 单元测试

覆盖率 —
    - record_metric 正常/异常/无效名称（sync）
    - record_metrics 批量（sync）
    - query_metrics 聚合查询（async）
    - get_metric_timeseries 时序查询（async）
    - get_dashboard_summary 仪表盘摘要（async）
    - VALID_METRIC_NAMES 校验（sync）
    - _date_trunc_day/_date_trunc_hour 跨数据库兼容（sync）

迁移说明（任务1 续作 - 服务层混合迁移测试）:
    query_metrics / get_metric_timeseries / get_dashboard_summary 已迁至 async，
    对应测试类改为 async def + async_db fixture。record_metric / record_metrics
    保持 sync，对应测试类不变。_date_trunc_* / _build_filters /
    _get_dialect_name 保持 sync 纯函数，对应测试类不变。
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.pipeline_metric import PipelineMetric, Base, VALID_METRIC_NAMES, FMEA_METRICS
from app.services import metrics_service
from app.utils.db_time import utcnow


@pytest.fixture
def db():
    """sync SQLite in-memory — 仅供 sync 测试类使用（TestRecordMetric 等）。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_db_context(db):
    """Mock get_db_context to use in-memory SQLite session（sync record_metric 测试用）。"""
    @contextmanager
    def _get_db_context():
        yield db
    return _get_db_context


async def _create_metric(
    db,
    *,
    metric_name: str = "low_confidence_pause",
    value: float = 1.0,
    project_id: int | None = None,
    iteration_id: int | None = None,
    run_id: int | None = None,
    step_name: str | None = None,
    detail: dict | None = None,
) -> PipelineMetric:
    """辅助：在 async_db 中直接创建 PipelineMetric 记录（绕过 record_metric）。"""
    metric = PipelineMetric(
        metric_name=metric_name,
        value=value,
        project_id=project_id,
        iteration_id=iteration_id,
        run_id=run_id,
        step_name=step_name,
        detail=detail,
    )
    db.add(metric)
    await db.flush()
    return metric


class TestRecordMetric:
    def test_record_single_metric(self, db, mock_db_context):
        with patch("app.db.database.get_db_context", mock_db_context):
            result = metrics_service.record_metric(
                "low_confidence_pause",
                project_id=1,
                iteration_id=10,
                run_id=100,
                step_name="reverse_infer",
                detail={"confidence": 0.5},
            )
        assert result is not None
        assert result.metric_name == "low_confidence_pause"
        assert result.value == 1.0
        assert result.project_id == 1
        assert result.iteration_id == 10
        assert result.run_id == 100
        assert result.step_name == "reverse_infer"
        assert result.detail == {"confidence": 0.5}

    def test_record_metric_with_custom_value(self, db, mock_db_context):
        with patch("app.db.database.get_db_context", mock_db_context):
            result = metrics_service.record_metric(
                "json_validation_failure",
                value=3.0,
                detail={"attempt": 2},
            )
        assert result is not None
        assert result.value == 3.0

    def test_record_metric_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Invalid metric name"):
            metrics_service.record_metric("nonexistent_metric")

    def test_record_metric_all_valid_names(self, db, mock_db_context):
        with patch("app.db.database.get_db_context", mock_db_context):
            for name in VALID_METRIC_NAMES:
                result = metrics_service.record_metric(name)
                assert result is not None
                assert result.metric_name == name

    def test_record_metric_db_failure_returns_none(self):
        with patch("app.db.database.get_db_context", side_effect=Exception("DB down")):
            result = metrics_service.record_metric("low_confidence_pause")
        assert result is None


class TestRecordMetrics:
    def test_batch_record(self, db, mock_db_context):
        metrics = [
            {"metric_name": "low_confidence_pause", "project_id": 1},
            {"metric_name": "json_validation_failure", "step_name": "backward_scan"},
            {"metric_name": "conflict_detected", "value": 2.0},
        ]
        with patch("app.db.database.get_db_context", mock_db_context):
            results = metrics_service.record_metrics(metrics)
        assert len(results) == 3

    def test_batch_record_skips_invalid(self, db, mock_db_context):
        metrics = [
            {"metric_name": "low_confidence_pause"},
            {"metric_name": "invalid_metric"},
            {"metric_name": "fallback_model_used"},
        ]
        with patch("app.db.database.get_db_context", mock_db_context):
            results = metrics_service.record_metrics(metrics)
        assert len(results) == 2

    def test_batch_record_empty(self):
        results = metrics_service.record_metrics([])
        assert results == []


class TestQueryMetrics:
    """聚合查询指标测试（async）"""

    async def test_query_all(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)
        await _create_metric(async_db, metric_name="json_validation_failure", project_id=1)

        result = await metrics_service.query_metrics(async_db)
        assert len(result) == 2
        lc = next(r for r in result if r["metric_name"] == "low_confidence_pause")
        assert lc["count"] == 2
        assert lc["total"] == 2.0
        assert lc["fmea_id"] == "F1"

    async def test_query_by_metric_name(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)
        await _create_metric(async_db, metric_name="json_validation_failure", project_id=1)

        result = await metrics_service.query_metrics(
            async_db, metric_name="low_confidence_pause"
        )
        assert len(result) == 1
        assert result[0]["metric_name"] == "low_confidence_pause"

    async def test_query_by_project_id(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=2)

        result = await metrics_service.query_metrics(async_db, project_id=1)
        assert len(result) == 1
        assert result[0]["count"] == 1

    async def test_query_by_iteration_id(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", iteration_id=10)
        await _create_metric(async_db, metric_name="low_confidence_pause", iteration_id=20)

        result = await metrics_service.query_metrics(async_db, iteration_id=10)
        assert len(result) == 1

    async def test_query_by_run_id(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", run_id=100)
        await _create_metric(async_db, metric_name="low_confidence_pause", run_id=200)

        result = await metrics_service.query_metrics(async_db, run_id=100)
        assert len(result) == 1

    async def test_query_with_time_filter(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause")

        since = utcnow() - timedelta(days=1)
        result = await metrics_service.query_metrics(async_db, since=since)
        assert len(result) >= 1

        future = utcnow() + timedelta(days=1)
        result = await metrics_service.query_metrics(async_db, since=future)
        assert len(result) == 0

    async def test_query_empty_db(self, async_db):
        result = await metrics_service.query_metrics(async_db)
        assert result == []


class TestGetMetricTimeseries:
    """时序查询指标测试（async）"""

    async def test_timeseries_day(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)

        since = utcnow() - timedelta(days=7)
        result = await metrics_service.get_metric_timeseries(
            async_db, "low_confidence_pause", project_id=1, since=since,
        )
        assert len(result) >= 1
        assert "time_bucket" in result[0]
        assert "count" in result[0]

    async def test_timeseries_hour(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)

        since = utcnow() - timedelta(hours=24)
        result = await metrics_service.get_metric_timeseries(
            async_db, "low_confidence_pause", project_id=1, since=since, interval="hour",
        )
        assert len(result) >= 1

    async def test_timeseries_no_data(self, async_db):
        since = utcnow() - timedelta(days=7)
        result = await metrics_service.get_metric_timeseries(
            async_db, "low_confidence_pause", since=since,
        )
        assert result == []


class TestGetDashboardSummary:
    """仪表盘摘要测试（async）"""

    async def test_summary_with_data(self, async_db):
        await _create_metric(async_db, metric_name="low_confidence_pause", project_id=1)
        await _create_metric(async_db, metric_name="json_validation_failure", project_id=1)

        since = utcnow() - timedelta(days=30)
        result = await metrics_service.get_dashboard_summary(
            async_db, project_id=1, since=since
        )
        assert "metrics" in result
        assert result["total_metric_types"] == len(FMEA_METRICS)
        assert result["active_metric_types"] == 2

    async def test_summary_empty(self, async_db):
        result = await metrics_service.get_dashboard_summary(async_db)
        assert result["total_metric_types"] == len(FMEA_METRICS)
        assert result["active_metric_types"] == 0

    async def test_summary_all_fmea_ids_present(self, async_db):
        result = await metrics_service.get_dashboard_summary(async_db)
        fmea_ids = [m["fmea_id"] for m in result["metrics"]]
        expected_ids = {"F1", "F2", "F3", "F5", "F9", "F11", "F12", "F13", "F14", "F15", "F16", "F17"}
        assert set(fmea_ids) == expected_ids


class TestFMEAMetadata:
    def test_all_metrics_have_fmea_id(self):
        for name, meta in FMEA_METRICS.items():
            assert "fmea_id" in meta
            assert "description" in meta
            assert meta["fmea_id"].startswith("F")

    def test_valid_metric_names_matches_fmea_metrics(self):
        assert VALID_METRIC_NAMES == set(FMEA_METRICS.keys())

    def test_ten_metric_types(self):
        assert len(FMEA_METRICS) == 12


class TestDateTruncCompat:
    """_date_trunc_* 辅助函数兼容性测试（sync SQLite）。"""

    def test_date_trunc_day_sqlite(self, db):
        expr = metrics_service._date_trunc_day(PipelineMetric.created_at, db)
        assert expr is not None

    def test_date_trunc_hour_sqlite(self, db):
        expr = metrics_service._date_trunc_hour(PipelineMetric.created_at, db)
        assert expr is not None

    def test_get_dialect_name_sqlite(self, db):
        name = metrics_service._get_dialect_name(db)
        assert name == "sqlite"

    def test_get_dialect_name_mysql(self):
        mock_db = MagicMock()
        mock_db.bind.dialect.name = "mysql"
        name = metrics_service._get_dialect_name(mock_db)
        assert name == "mysql"

    def test_get_dialect_name_exception_returns_mysql(self):
        mock_db = MagicMock(spec=[])
        name = metrics_service._get_dialect_name(mock_db)
        assert name == "mysql"
