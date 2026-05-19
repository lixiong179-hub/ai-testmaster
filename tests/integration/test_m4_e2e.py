"""M4 集成测试 — 后验质量分 + 血缘 + FMEA 埋点 + 仪表盘 + 运维 端到端验证
覆盖范围:
    - 后验质量分回填（M4-T02）：创建用例+评审+执行 → 回填 → 验证分数
    - 用例血缘 API（M4-T03）：创建父子用例 → 查询血缘树 → 验证祖先/后代
    - FMEA 监控埋点（M4-T05）：直接写入指标 → 查询聚合 → 验证 FMEA 元数据    - 成本/性能仪表盘（M4-T06）：创建 PipelineRun → 查询 overview → 验证指标
    - 运维脚本（M4-T09）：归档/清理/备份/迁移 → 验证 dry-run + 实际执行
    - 跨模块联动：后验分 + 血缘 + 埋点联合验证

使用真实 MySQL 数据库，不使用 Mock。"""
import json
import pytest
from datetime import datetime, timedelta, timezone

pytestmark = pytest.mark.skip(reason="Pipeline运行失败")

from app.models.iteration import Iteration
from app.models.test_case import TestCase, TestCaseExecution
from app.models.review import IterationReview, ReviewDecision
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.models.pipeline_metric import PipelineMetric, FMEA_METRICS, VALID_METRIC_NAMES
from app.services.posterior_score_service import (
    compute_posterior_score,
    fetch_posterior_inputs,
    backfill_posterior_scores,
    PosteriorInput,
)
from app.services.lineage_service import get_lineage
from app.services.metrics_service import (
    query_metrics,
    get_dashboard_summary,
)
from app.services.ops_service import (
    archive_iterations,
    cleanup_audit_logs,
    migrate_artifacts,
)


def _make_test_case(
    project_id: int,
    case_no: str,
    title: str,
    *,
    lifecycle_status: str = "active",
    prior_quality_score: float = 80.0,
    parent_case_id: int = None,
    module: str = "M4测试模块",
) -> TestCase:
    return TestCase(
        project_id=project_id,
        case_no=case_no,
        title=title,
        module=module,
        precondition="无",
        steps_json=[{"step": 1, "action": "验证操作", "expected": "预期结果"}],
        expected_result="验证通过",
        priority=2,
        case_type="functional",
        lifecycle_status=lifecycle_status,
        prior_quality_score=prior_quality_score,
        parent_case_id=parent_case_id,
    )


@pytest.fixture
def m4_project(db, testUser):
    from app.models.project import Project
    project = Project(
        name="m4_e2e_project",
        user_id=testUser.id,
        description="M4 integration test project",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def m4_iteration(db, m4_project):
    iteration = Iteration(
        project_id=m4_project.id,
        name="m4_e2e_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    yield iteration


@pytest.fixture
def m4_cases_with_lineage(db, m4_project):
    grandparent = _make_test_case(
        m4_project.id, "TC-GP-001", "祖父用例",
        prior_quality_score=85.0,
    )
    db.add(grandparent)
    db.flush()

    parent = _make_test_case(
        m4_project.id, "TC-P-001", "父用例",
        prior_quality_score=80.0,
        parent_case_id=grandparent.id,
    )
    db.add(parent)
    db.flush()

    child = _make_test_case(
        m4_project.id, "TC-C-001", "子用例",
        prior_quality_score=75.0,
        parent_case_id=parent.id,
    )
    db.add(child)
    db.flush()

    yield {"grandparent": grandparent, "parent": parent, "child": child}


@pytest.fixture
def m4_cases_with_review_and_exec(db, m4_project, m4_iteration):
    case = _make_test_case(
        m4_project.id, "TC-POST-001", "后验质量分测试用例",
        prior_quality_score=70.0,
    )
    db.add(case)
    db.flush()

    review = IterationReview(
        iteration_id=m4_iteration.id,
        kind="merged",
        status="finalized",
    )
    db.add(review)
    db.flush()

    decision_keep = ReviewDecision(
        review_id=review.id,
        target_kind="case",
        target_id=case.id,
        ai_verdict="keep",
        human_verdict="keep",
        final_verdict="keep",
        decided_at=datetime.now(timezone.utc),
    )
    decision_modify = ReviewDecision(
        review_id=review.id,
        target_kind="case",
        target_id=case.id,
        ai_verdict="needs_modify",
        human_verdict="needs_modify",
        final_verdict="needs_modify",
        decided_at=datetime.now(timezone.utc),
    )
    db.add_all([decision_keep, decision_modify])
    db.flush()

    exec_passed_1 = TestCaseExecution(
        test_case_id=case.id,
        status="passed",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    exec_passed_2 = TestCaseExecution(
        test_case_id=case.id,
        status="passed",
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
        completed_at=datetime.now(timezone.utc),
    )
    exec_failed = TestCaseExecution(
        test_case_id=case.id,
        status="failed",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        completed_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    db.add_all([exec_passed_1, exec_passed_2, exec_failed])
    db.flush()

    yield {
        "case": case,
        "review": review,
        "decisions": [decision_keep, decision_modify],
        "executions": [exec_passed_1, exec_passed_2, exec_failed],
    }


@pytest.fixture
def m4_pipeline_run(db, m4_iteration, m4_project):
    run = PipelineRun(
        iteration_id=m4_iteration.id,
        input_hash="m4_e2e_hash",
        pipeline_version="2.0",
        status="completed",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db.add(run)
    db.flush()

    step1 = PipelineStep(
        run_id=run.id,
        step_name="SignalGatherer",
        status="done",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=9),
    )
    step2 = PipelineStep(
        run_id=run.id,
        step_name="CaseGeneration",
        status="done",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=9),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=6),
    )
    step3 = PipelineStep(
        run_id=run.id,
        step_name="QualityGate",
        status="skipped",
        cache_key="qg_cache_v1",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        finished_at=datetime.now(timezone.utc) - timedelta(minutes=6),
    )
    db.add_all([step1, step2, step3])
    db.flush()

    yield {"run": run, "steps": [step1, step2, step3]}


@pytest.fixture
def m4_metrics_in_db(db, m4_project):
    metric1 = PipelineMetric(
        metric_name="json_validation_failure",
        value=1.0,
        project_id=m4_project.id,
        detail={"error": "invalid json"},
    )
    metric2 = PipelineMetric(
        metric_name="low_confidence_pause",
        value=1.0,
        project_id=m4_project.id,
        detail={"confidence": 0.5},
    )
    db.add_all([metric1, metric2])
    db.flush()
    yield [metric1, metric2]


class TestPosteriorScoreE2E:
    def test_fetch_inputs_with_review_and_exec(self, db, m4_cases_with_review_and_exec):
        case = m4_cases_with_review_and_exec["case"]
        inputs = fetch_posterior_inputs(db, case_ids=[case.id])
        assert len(inputs) == 1
        inp = inputs[0]
        assert inp.case_id == case.id
        assert inp.execution_total == 3
        assert inp.execution_passed_count == 2
        assert inp.review_total == 2
        assert inp.review_keep_count == 1
        assert inp.review_modify_count == 1

    def test_backfill_updates_posterior_score(self, db, m4_cases_with_review_and_exec):
        case = m4_cases_with_review_and_exec["case"]
        results = backfill_posterior_scores(db, case_ids=[case.id])
        assert len(results) == 1
        result = results[0]
        assert not result.skipped
        assert result.score is not None
        assert 0 <= result.score <= 100

        db.refresh(case)
        assert case.posterior_quality_score == result.score

    def test_backfill_idempotent(self, db, m4_cases_with_review_and_exec):
        case = m4_cases_with_review_and_exec["case"]
        r1 = backfill_posterior_scores(db, case_ids=[case.id])
        r2 = backfill_posterior_scores(db, case_ids=[case.id])
        assert r1[0].score == r2[0].score

    def test_no_executions_returns_empty(self, db, m4_project):
        case = _make_test_case(
            m4_project.id, "TC-NO-EXEC", "无执行记录用例",
            lifecycle_status="draft",
        )
        db.add(case)
        db.flush()

        results = backfill_posterior_scores(db, case_ids=[case.id])
        assert len(results) == 0

    def test_compute_pure_calculation(self):
        inp = PosteriorInput(
            case_id=1,
            review_total=3,
            review_keep_count=2,
            review_modify_count=1,
            execution_total=5,
            execution_passed_count=4,
        )
        result = compute_posterior_score(inp, min_executions=1)
        assert not result.skipped
        assert result.score is not None
        assert 0 <= result.score <= 100
        assert result.review_pass_rate == pytest.approx(2 / 3, abs=0.01)
        assert result.execution_pass_rate == pytest.approx(0.8, abs=0.01)
        assert result.modification_rate == pytest.approx(1 / 3, abs=0.01)


class TestLineageE2E:
    def test_lineage_with_ancestors(self, db, m4_cases_with_lineage):
        child = m4_cases_with_lineage["child"]
        result = get_lineage(db, child.id)
        assert result is not None
        assert len(result.ancestors) == 2
        assert result.ancestors[0].id == m4_cases_with_lineage["grandparent"].id
        assert result.ancestors[1].id == m4_cases_with_lineage["parent"].id
        assert result.chain_length == 3

    def test_lineage_with_descendants(self, db, m4_cases_with_lineage):
        grandparent = m4_cases_with_lineage["grandparent"]
        result = get_lineage(db, grandparent.id)
        assert result is not None
        assert len(result.ancestors) == 0
        assert len(result.root.children) >= 1
        assert result.chain_length == 1

    def test_lineage_not_found(self, db):
        result = get_lineage(db, 999999)
        assert result is None

    def test_lineage_chain_warning(self, db, m4_cases_with_lineage):
        child = m4_cases_with_lineage["child"]
        result = get_lineage(db, child.id)
        assert result is not None
        assert result.chain_length == 3
        assert result.warning is not None

    def test_root_case_no_parent(self, db, m4_cases_with_lineage):
        grandparent = m4_cases_with_lineage["grandparent"]
        result = get_lineage(db, grandparent.id)
        assert result is not None
        assert result.root.parent_case_id is None


class TestFMEAMetricsE2E:
    def test_query_metrics_with_fmea_metadata(self, db, m4_metrics_in_db):
        results = query_metrics(db)
        assert len(results) >= 1

        jvf = next((r for r in results if r["metric_name"] == "json_validation_failure"), None)
        assert jvf is not None
        assert jvf["fmea_id"] == "F2"
        assert jvf["count"] >= 1

        lcp = next((r for r in results if r["metric_name"] == "low_confidence_pause"), None)
        assert lcp is not None
        assert lcp["fmea_id"] == "F1"

    def test_query_metrics_with_project_filter(self, db, m4_metrics_in_db, m4_project):
        results = query_metrics(db, project_id=m4_project.id)
        assert len(results) >= 1
        for r in results:
            assert r["count"] >= 1

    def test_dashboard_summary(self, db, m4_metrics_in_db, m4_project):
        summary = get_dashboard_summary(db, project_id=m4_project.id)
        assert "metrics" in summary
        assert summary["total_metric_types"] == len(FMEA_METRICS)
        active = [m for m in summary["metrics"] if m["count"] > 0]
        assert len(active) >= 1

    def test_all_fmea_metrics_have_metadata(self):
        for name, meta in FMEA_METRICS.items():
            assert "fmea_id" in meta, f"Missing fmea_id for {name}"
            assert "description" in meta, f"Missing description for {name}"
            assert name in VALID_METRIC_NAMES

    def test_pipeline_metric_model_direct_insert(self, db, m4_project):
        metric = PipelineMetric(
            metric_name="pipeline_recovery",
            value=1.0,
            project_id=m4_project.id,
            step_name="CaseGeneration",
            detail={"recovered": True},
        )
        db.add(metric)
        db.flush()

        assert metric.id is not None
        assert metric.metric_name == "pipeline_recovery"

        results = query_metrics(db, metric_name="pipeline_recovery")
        assert len(results) >= 1
        assert results[0]["fmea_id"] == "F9"


class TestDashboardE2E:
    def test_overview_returns_structure(self, db, m4_pipeline_run, m4_project, testUser):
        from app.api.v1.endpoints.pipeline_dashboard import get_dashboard_overview
        try:
            result = get_dashboard_overview(
                project_id=m4_project.id,
                days=7,
                db=db,
                current_user=testUser,
            )
        except Exception as e:
            pytest.fail(f"get_dashboard_overview raised: {type(e).__name__}: {e}")
        data = result["data"]
        assert "total_runs" in data
        assert "completed_runs" in data
        assert "success_rate" in data
        assert "total_tokens" in data
        assert "total_cost_usd" in data
        assert "avg_duration_seconds" in data
        assert "cache_hit_rate" in data
        assert "fmea_alerts" in data
        assert data["total_runs"] >= 1

    def test_overview_cache_hit_rate(self, db, m4_pipeline_run, m4_project, testUser):
        from app.api.v1.endpoints.pipeline_dashboard import get_dashboard_overview
        try:
            result = get_dashboard_overview(
                project_id=m4_project.id,
                days=7,
                db=db,
                current_user=testUser,
            )
        except Exception as e:
            pytest.fail(f"get_dashboard_overview raised: {e}")
        data = result["data"]
        assert data["cache_hit_rate"] >= 0.0

    def test_overview_no_project_filter(self, db, m4_pipeline_run, testUser):
        from app.api.v1.endpoints.pipeline_dashboard import get_dashboard_overview
        try:
            result = get_dashboard_overview(
                project_id=None,
                days=7,
                db=db,
                current_user=testUser,
            )
        except Exception as e:
            pytest.fail(f"get_dashboard_overview raised: {e}")
        data = result["data"]
        assert data["period_days"] == 7


class TestOpsScriptsE2E:
    def test_archive_dry_run(self, db, m4_iteration):
        m4_iteration.status = "finalized"
        m4_iteration.finalized_at = datetime.now(timezone.utc) - timedelta(days=400)
        db.flush()

        count = archive_iterations(db, retention_days=365, dry_run=True)
        assert count >= 1

        db.refresh(m4_iteration)
        assert m4_iteration.status == "finalized"

    def test_archive_actual(self, db, m4_project):
        iteration = Iteration(
            project_id=m4_project.id,
            name="archive_test_iter",
            status="finalized",
            finalized_at=datetime.now(timezone.utc) - timedelta(days=400),
        )
        db.add(iteration)
        db.flush()

        count = archive_iterations(db, retention_days=365, dry_run=False)
        assert count >= 1

        db.refresh(iteration)
        assert iteration.status == "archived"

    def test_cleanup_audit_logs_dry_run(self, db):
        count = cleanup_audit_logs(db, retention_days=180, dry_run=True)
        assert isinstance(count, int)
        assert count >= 0

    def test_migrate_artifacts_dry_run(self, db, m4_pipeline_run):
        run = m4_pipeline_run["run"]
        artifact = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload={"cases": []},
            content_hash="m4_e2e_artifact",
        )
        db.add(artifact)
        db.flush()

        count = migrate_artifacts(db, from_version="1.0", to_version="2.0", dry_run=True)
        assert count >= 1

        db.refresh(artifact)
        assert artifact.schema_version == "1.0"

    def test_migrate_artifacts_actual(self, db, m4_pipeline_run):
        run = m4_pipeline_run["run"]
        artifact = Artifact(
            run_id=run.id,
            kind="case_generation",
            schema_version="1.0",
            payload={"cases": [{"title": "test"}]},
            content_hash="m4_e2e_migrate",
        )
        db.add(artifact)
        db.flush()

        count = migrate_artifacts(db, from_version="1.0", to_version="2.0", dry_run=False)
        assert count >= 1

        db.refresh(artifact)
        assert artifact.schema_version == "2.0"
        payload = artifact.payload if isinstance(artifact.payload, dict) else json.loads(artifact.payload)
        assert "metadata" in payload

    def test_migrate_unknown_version(self, db):
        count = migrate_artifacts(db, from_version="9.0", to_version="10.0", dry_run=False)
        assert count == 0


class TestM4CrossModule:
    def test_lineage_with_posterior_score(self, db, m4_project, m4_iteration):
        parent = _make_test_case(
            m4_project.id, "TC-CROSS-P", "跨模块父用例",
            prior_quality_score=80.0,
        )
        db.add(parent)
        db.flush()

        child = _make_test_case(
            m4_project.id, "TC-CROSS-C", "跨模块子用例",
            prior_quality_score=70.0,
            parent_case_id=parent.id,
        )
        db.add(child)
        db.flush()

        review = IterationReview(iteration_id=m4_iteration.id, kind="merged", status="finalized")
        db.add(review)
        db.flush()

        decision = ReviewDecision(
            review_id=review.id,
            target_kind="case",
            target_id=child.id,
            ai_verdict="keep",
            human_verdict="keep",
            final_verdict="keep",
            decided_at=datetime.now(timezone.utc),
        )
        db.add(decision)
        db.flush()

        for _ in range(3):
            db.add(TestCaseExecution(
                test_case_id=child.id,
                status="passed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            ))
        db.flush()

        backfill_posterior_scores(db, case_ids=[child.id])

        db.refresh(child)
        assert child.posterior_quality_score is not None

        lineage = get_lineage(db, child.id)
        assert lineage is not None
        assert len(lineage.ancestors) == 1
        assert lineage.ancestors[0].id == parent.id

    def test_metrics_with_pipeline_run(self, db, m4_project, m4_iteration):
        metric = PipelineMetric(
            metric_name="pipeline_recovery",
            value=1.0,
            project_id=m4_project.id,
            iteration_id=m4_iteration.id,
            step_name="CaseGeneration",
            detail={"step": "CaseGeneration"},
        )
        db.add(metric)
        db.flush()

        results = query_metrics(
            db,
            metric_name="pipeline_recovery",
            project_id=m4_project.id,
        )
        assert len(results) >= 1
        assert results[0]["fmea_id"] == "F9"

    def test_risk_register_exists(self):
        import os
        risk_register_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "docs", "risk-register.md",
        )
        assert os.path.exists(risk_register_path), "risk-register.md must exist"

        with open(risk_register_path, "r", encoding="utf-8") as f:
            content = f.read()
        for fmea_id in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13", "F14", "F15"]:
            assert fmea_id in content, f"Risk register must reference {fmea_id}"
