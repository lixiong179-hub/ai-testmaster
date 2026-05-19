"""M4-T06 Pipeline 仪表盘聚合 API 单元测试

覆盖率    - get_dashboard_overview 总览指标
    - get_token_usage 每日 Token 消耗    - get_run_duration 平均运行时长
    - get_step_latency — Step 耗时分布
    - get_cache_hit_rate 缓存命中率"""
import pytest
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.pipeline import PipelineRun, PipelineStep, Base as PipelineBase
from app.models.pipeline_metric import PipelineMetric, Base as MetricBase
from app.ai.call_log import AICallLog, Base as CallLogBase
from app.models.iteration import Iteration, Base as IterationBase
from app.models.project import Project, Base as ProjectBase
from app.models.user import User, Base as UserBase
from app.utils.db_time import utcnow


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    for base in [ProjectBase, IterationBase, PipelineBase, MetricBase, CallLogBase, UserBase]:
        base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(username="admin", email="admin@test.com", password_hash="hash", is_active=True)
    session.add(user)
    session.commit()
    yield session
    session.close()


def _get_user(db) -> User:
    return db.query(User).filter(User.username == "admin").first()


def _make_project(db) -> Project:
    user = _get_user(db)
    project = Project(name=f"TestProject_{id(db)}", user_id=user.id, description="test")
    db.add(project)
    db.commit()
    return project


def _make_iteration(db, project_id: int) -> Iteration:
    iteration = Iteration(project_id=project_id, name="Sprint 1", status="draft")
    db.add(iteration)
    db.commit()
    return iteration


def _make_run(db, iteration_id: int, status: str = "completed") -> PipelineRun:
    now = utcnow()
    run = PipelineRun(
        iteration_id=iteration_id,
        input_hash="abc123",
        pipeline_version="2.0",
        status=status,
        started_at=now - timedelta(minutes=5),
        finished_at=now if status == "completed" else None,
    )
    db.add(run)
    db.commit()
    return run


def _make_step(db, run_id: int, step_name: str, status: str = "done") -> PipelineStep:
    now = utcnow()
    step = PipelineStep(
        run_id=run_id,
        step_name=step_name,
        step_version="1.0",
        status=status,
        cache_key="cache_key_1" if status == "skipped" else None,
        started_at=now - timedelta(minutes=2),
        finished_at=now if status in ("done", "skipped") else None,
    )
    db.add(step)
    db.commit()
    return step


def _make_call_log(db, run_id: int) -> AICallLog:
    log = AICallLog(
        run_id=run_id,
        step_name="backward_scan",
        model="deepseek-v4-flash",
        prompt_tokens=1000,
        completion_tokens=500,
        cost_usd=0.01,
        latency_ms=3000,
        status="success",
    )
    db.add(log)
    db.commit()
    return log


class TestDashboardOverview:
    def test_overview_empty(self, db):
        from app.api.v1.endpoints.pipeline_dashboard import get_dashboard_overview
        result = get_dashboard_overview(db=db, project_id=None, days=7, current_user=_get_user(db))
        data = result["data"]
        assert data["total_runs"] == 0
        assert data["success_rate"] == 0.0
        assert data["total_tokens"] == 0

    def test_overview_with_data(self, db):
        project = _make_project(db)
        iteration = _make_iteration(db, project.id)
        run = _make_run(db, iteration.id)
        _make_step(db, run.id, "backward_scan")
        _make_call_log(db, run.id)

        from app.api.v1.endpoints.pipeline_dashboard import get_dashboard_overview
        result = get_dashboard_overview(db=db, project_id=None, days=7, current_user=_get_user(db))
        data = result["data"]
        assert data["total_runs"] >= 1
        assert data["total_tokens"] >= 1500

    def test_overview_with_project_filter(self, db):
        project = _make_project(db)
        iteration = _make_iteration(db, project.id)
        run = _make_run(db, iteration.id)
        _make_call_log(db, run.id)

        from app.api.v1.endpoints.pipeline_dashboard import get_dashboard_overview
        result = get_dashboard_overview(db=db, project_id=project.id, days=7, current_user=_get_user(db))
        data = result["data"]
        assert data["total_runs"] >= 1


class TestTokenUsage:
    def test_token_usage_empty(self, db):
        from app.api.v1.endpoints.pipeline_dashboard import get_token_usage
        result = get_token_usage(db=db, project_id=None, days=7, current_user=_get_user(db))
        assert result["data"] == {}

    def test_token_usage_with_data(self, db):
        project = _make_project(db)
        iteration = _make_iteration(db, project.id)
        run = _make_run(db, iteration.id)
        _make_call_log(db, run.id)

        from app.api.v1.endpoints.pipeline_dashboard import get_token_usage
        result = get_token_usage(db=db, project_id=None, days=7, current_user=_get_user(db))
        data = result["data"]
        assert len(data) >= 1
        assert data[0]["total_tokens"] >= 1500


class TestRunDuration:
    def test_run_duration_empty(self, db):
        from app.api.v1.endpoints.pipeline_dashboard import get_run_duration
        result = get_run_duration(db=db, project_id=None, days=7, current_user=_get_user(db))
        assert result["data"] == {}

    def test_run_duration_with_data(self, db):
        project = _make_project(db)
        iteration = _make_iteration(db, project.id)
        _make_run(db, iteration.id, "completed")

        from app.api.v1.endpoints.pipeline_dashboard import get_run_duration
        result = get_run_duration(db=db, project_id=None, days=7, current_user=_get_user(db))
        data = result["data"]
        assert len(data) >= 1


class TestStepLatency:
    def test_step_latency_empty(self, db):
        from app.api.v1.endpoints.pipeline_dashboard import get_step_latency
        result = get_step_latency(db=db, project_id=None, days=7, current_user=_get_user(db))
        assert result["data"] == {}

    def test_step_latency_with_data(self, db):
        project = _make_project(db)
        iteration = _make_iteration(db, project.id)
        run = _make_run(db, iteration.id)
        _make_step(db, run.id, "backward_scan", "done")

        from app.api.v1.endpoints.pipeline_dashboard import get_step_latency
        result = get_step_latency(db=db, project_id=None, days=7, current_user=_get_user(db))
        data = result["data"]
        assert len(data) >= 1
        assert data[0]["step_name"] == "backward_scan"


class TestCacheHitRate:
    def test_cache_hit_rate_empty(self, db):
        from app.api.v1.endpoints.pipeline_dashboard import get_cache_hit_rate
        result = get_cache_hit_rate(db=db, project_id=None, days=7, current_user=_get_user(db))
        assert result["data"] == {}

    def test_cache_hit_rate_with_data(self, db):
        project = _make_project(db)
        iteration = _make_iteration(db, project.id)
        run = _make_run(db, iteration.id)
        _make_step(db, run.id, "backward_scan", "done")
        _make_step(db, run.id, "forward_scan", "skipped")

        from app.api.v1.endpoints.pipeline_dashboard import get_cache_hit_rate
        result = get_cache_hit_rate(db=db, project_id=None, days=7, current_user=_get_user(db))
        data = result["data"]
        assert len(data) >= 1
