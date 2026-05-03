"""Pipeline API 数据结构验证测试

覆盖范围:
    - pipeline_service.get_run 返回数据结构验证
    - steps 字段完整性（step_name/status/degraded/retried_count）
    - artifacts 字段完整性（kind/confidence/schema_version）
    - 不存在的 run_id 返回 None
    - run 基础字段（iteration_id/pipeline_version/input_hash）

使用真实 MySQL 数据库，复用 conftest 中的 testProject/testUser fixture。
"""
import pytest

from app.models.iteration import Iteration
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.services import pipeline_service


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="pipeline_struct_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def test_run(db, test_iteration):
    run = pipeline_service.create_run(
        db=db,
        iteration_id=test_iteration.id,
        input_hash="struct_test_hash_001",
        pipeline_version="1.0",
    )
    db.flush()

    step1 = PipelineStep(
        run_id=run.id,
        step_name="signal_gatherer",
        step_version="1.0",
        status="done",
        retried_count=0,
        degraded=False,
    )
    db.add(step1)
    db.flush()

    step2 = PipelineStep(
        run_id=run.id,
        step_name="case_generation",
        step_version="1.0",
        status="running",
        retried_count=1,
        degraded=True,
    )
    db.add(step2)
    db.flush()

    artifact1 = Artifact(
        run_id=run.id,
        kind="raw_signals",
        schema_version="1.0",
        payload={"has_prd": True, "has_ui": False},
        confidence=0.85,
        content_hash="struct_test_artifact_001",
    )
    db.add(artifact1)
    db.flush()

    db.commit()
    db.refresh(run)
    return run


class TestPipelineRunStructure:
    def test_get_run_returns_run_object(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert run is not None
        assert run.id == test_run.id
        assert run.status in ("pending", "running", "completed", "failed", "waiting_for_user", "cancelled")

    def test_steps_are_accessible(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert len(run.steps) >= 1

    def test_step_fields_complete(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        step = run.steps[0]
        assert hasattr(step, "step_name")
        assert hasattr(step, "status")
        assert hasattr(step, "started_at")
        assert hasattr(step, "finished_at")
        assert hasattr(step, "error")
        assert hasattr(step, "retried_count")
        assert hasattr(step, "degraded")

    def test_step_degraded_flag(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        case_gen_steps = [s for s in run.steps if s.step_name == "case_generation"]
        assert len(case_gen_steps) == 1
        assert case_gen_steps[0].degraded is True
        assert case_gen_steps[0].retried_count == 1

    def test_step_done_status(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        sg_steps = [s for s in run.steps if s.step_name == "signal_gatherer"]
        assert len(sg_steps) == 1
        assert sg_steps[0].status == "done"
        assert sg_steps[0].degraded is False

    def test_artifacts_are_accessible(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert len(run.artifacts) >= 1

    def test_artifact_fields_complete(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        artifact = run.artifacts[0]
        assert hasattr(artifact, "kind")
        assert hasattr(artifact, "confidence")
        assert hasattr(artifact, "schema_version")
        assert hasattr(artifact, "created_at")

    def test_artifact_confidence_value(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        raw_signals = [a for a in run.artifacts if a.kind == "raw_signals"]
        assert len(raw_signals) == 1
        assert raw_signals[0].confidence == 0.85

    def test_nonexistent_run_returns_none(self, db):
        run = pipeline_service.get_run(db, 999999)
        assert run is None

    def test_run_has_iteration_id(self, db, test_run, test_iteration):
        run = pipeline_service.get_run(db, test_run.id)
        assert run.iteration_id == test_iteration.id

    def test_run_has_pipeline_version(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert run.pipeline_version == "1.0"

    def test_run_has_input_hash(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert run.input_hash == "struct_test_hash_001"
