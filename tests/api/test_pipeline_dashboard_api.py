import pytest
from datetime import timedelta

from app.models.pipeline import PipelineRun, PipelineStep
from app.models.pipeline_metric import PipelineMetric
from app.ai.call_log import AICallLog
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.user import User
from app.utils.db_time import utcnow


@pytest.fixture
def dash_user(db):
    user = User(username="dash_api_user", email="dash_api@test.com", password_hash="hash", is_active=True)
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    try:
        db.query(AICallLog).filter(
            AICallLog.run_id.in_(
                db.query(PipelineRun.id).filter(
                    PipelineRun.iteration_id.in_(
                        db.query(Iteration.id).filter(
                            Iteration.project_id.in_(
                                db.query(Project.id).filter(Project.user_id == user.id)
                            )
                        )
                    )
                )
            )
        ).delete(synchronize_session=False)
        db.query(PipelineStep).filter(
            PipelineStep.run_id.in_(
                db.query(PipelineRun.id).filter(
                    PipelineRun.iteration_id.in_(
                        db.query(Iteration.id).filter(
                            Iteration.project_id.in_(
                                db.query(Project.id).filter(Project.user_id == user.id)
                            )
                        )
                    )
                )
            )
        ).delete(synchronize_session=False)
        db.query(PipelineMetric).filter(
            PipelineMetric.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(PipelineRun).filter(
            PipelineRun.iteration_id.in_(
                db.query(Iteration.id).filter(
                    Iteration.project_id.in_(
                        db.query(Project.id).filter(Project.user_id == user.id)
                    )
                )
            )
        ).delete(synchronize_session=False)
        db.query(Iteration).filter(
            Iteration.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture
def dash_project(db, dash_user):
    project = Project(name="dash_api_project", user_id=dash_user.id, description="dash test", status=1, project_type="web")
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_iteration(db, project_id):
    iteration = Iteration(project_id=project_id, name=f"Sprint_{id(db)}", status="draft")
    db.add(iteration)
    db.flush()
    db.refresh(iteration)
    return iteration


def _make_run(db, iteration_id, status="completed"):
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
    db.flush()
    db.refresh(run)
    return run


def _make_step(db, run_id, step_name="backward_scan", status="done"):
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
    db.flush()
    db.refresh(step)
    return step


def _make_call_log(db, run_id):
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
    db.flush()
    db.refresh(log)
    return log


class TestDashboardOverviewAPI:

    def test_overview_empty(self, client, authHeaders):
        response = client.get("/api/v1/pipeline/dashboard/overview", headers=authHeaders)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_runs"] == 0
        assert data["success_rate"] == 0.0

    def test_overview_with_data(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        run = _make_run(db, iteration.id)
        _make_step(db, run.id)
        _make_call_log(db, run.id)
        response = client.get("/api/v1/pipeline/dashboard/overview", headers=authHeaders)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_runs"] >= 1

    def test_overview_with_project_filter(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        run = _make_run(db, iteration.id)
        _make_call_log(db, run.id)
        response = client.get(
            "/api/v1/pipeline/dashboard/overview",
            params={"project_id": dash_project.id},
            headers=authHeaders,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_runs"] >= 1

    def test_overview_unauthenticated(self, client):
        response = client.get("/api/v1/pipeline/dashboard/overview")
        assert response.status_code == 401

    def test_overview_days_param(self, client, authHeaders):
        response = client.get(
            "/api/v1/pipeline/dashboard/overview",
            params={"days": 30},
            headers=authHeaders,
        )
        assert response.status_code == 200


class TestTokenUsageAPI:

    def test_token_usage_empty(self, client, authHeaders):
        response = client.get("/api/v1/pipeline/token-usage", headers=authHeaders)
        assert response.status_code == 200

    def test_token_usage_with_data(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        run = _make_run(db, iteration.id)
        _make_call_log(db, run.id)
        response = client.get("/api/v1/pipeline/token-usage", headers=authHeaders)
        assert response.status_code == 200

    def test_token_usage_with_project_filter(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        run = _make_run(db, iteration.id)
        _make_call_log(db, run.id)
        response = client.get(
            "/api/v1/pipeline/token-usage",
            params={"project_id": dash_project.id},
            headers=authHeaders,
        )
        assert response.status_code == 200


class TestRunDurationAPI:

    def test_run_duration_empty(self, client, authHeaders):
        response = client.get("/api/v1/pipeline/run-duration", headers=authHeaders)
        assert response.status_code == 200

    def test_run_duration_with_data(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        _make_run(db, iteration.id, "completed")
        response = client.get("/api/v1/pipeline/run-duration", headers=authHeaders)
        assert response.status_code == 200


class TestStepLatencyAPI:

    def test_step_latency_empty(self, client, authHeaders):
        response = client.get("/api/v1/pipeline/step-latency", headers=authHeaders)
        assert response.status_code == 200

    def test_step_latency_with_data(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        run = _make_run(db, iteration.id)
        _make_step(db, run.id, "backward_scan", "done")
        response = client.get("/api/v1/pipeline/step-latency", headers=authHeaders)
        assert response.status_code == 200


class TestCacheHitRateAPI:

    def test_cache_hit_rate_empty(self, client, authHeaders):
        response = client.get("/api/v1/pipeline/cache-hit-rate", headers=authHeaders)
        assert response.status_code == 200

    def test_cache_hit_rate_with_data(self, client, authHeaders, db, dash_project):
        iteration = _make_iteration(db, dash_project.id)
        run = _make_run(db, iteration.id)
        _make_step(db, run.id, "backward_scan", "done")
        _make_step(db, run.id, "forward_scan", "skipped")
        response = client.get("/api/v1/pipeline/cache-hit-rate", headers=authHeaders)
        assert response.status_code == 200
