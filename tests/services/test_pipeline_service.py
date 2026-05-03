"""pipeline_service 单元测试

覆盖范围:
    - create_run: 幂等校验、iteration_id 不存在
    - update_run_status: 合法/非法状态迁移
    - create_step: run_id 不存在
    - update_step_status: 合法/非法状态迁移、retried_count/degraded 更新
    - create_artifact: 重复 hash、run_id 不存在
    - find_cached_step: 命中/未命中
    - compute_input_hash / compute_cache_key
    - increment_step_retried_count
    - update_step_output_artifact_ids
    - list_runs
    - get_artifact_by_hash

使用真实 MySQL 数据库。
"""
import pytest

from app.models.iteration import Iteration, IterationInput
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.services import pipeline_service
from app.services.pipeline_service import (
    DuplicateArtifactHashError,
    PipelineRunValidationError,
    PipelineStepValidationError,
    PipelineStatusTransitionError,
    compute_input_hash,
    compute_cache_key,
)


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="psvc_test_iter",
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
        input_hash="psvc_test_hash",
        pipeline_version="1.0",
    )
    db.flush()
    return run


class TestCreateRun:
    def test_idempotent_same_hash_running(self, db, test_iteration):
        run1 = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="idem_hash",
            pipeline_version="1.0",
        )
        db.flush()
        pipeline_service.update_run_status(db=db, run_id=run1.id, status="running")
        run2 = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="idem_hash",
            pipeline_version="1.0",
        )
        db.flush()
        assert run1.id == run2.id

    def test_different_hash_creates_new(self, db, test_iteration):
        run1 = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="hash_a",
            pipeline_version="1.0",
        )
        db.flush()
        run2 = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="hash_b",
            pipeline_version="1.0",
        )
        db.flush()
        assert run1.id != run2.id

    def test_nonexistent_iteration_raises(self, db):
        with pytest.raises(PipelineRunValidationError):
            pipeline_service.create_run(
                db=db,
                iteration_id=999999,
                input_hash="x",
                pipeline_version="1.0",
            )


class TestUpdateRunStatus:
    def test_pending_to_running(self, db, test_run):
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="running",
        )
        assert updated is not None
        assert updated.status == "running"
        assert updated.started_at is not None

    def test_running_to_completed(self, db, test_run):
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="running")
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="completed",
        )
        assert updated.status == "completed"
        assert updated.finished_at is not None

    def test_running_to_failed_with_error(self, db, test_run):
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="running")
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="failed", error="OOM",
        )
        assert updated.status == "failed"
        assert updated.error == "OOM"
        assert updated.finished_at is not None

    def test_running_to_waiting_for_user(self, db, test_run):
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="running")
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="waiting_for_user",
        )
        assert updated.status == "waiting_for_user"

    def test_waiting_to_running(self, db, test_run):
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="running")
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="waiting_for_user")
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="running",
        )
        assert updated.status == "running"

    def test_waiting_to_cancelled(self, db, test_run):
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="running")
        pipeline_service.update_run_status(db=db, run_id=test_run.id, status="waiting_for_user")
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="cancelled",
        )
        assert updated.status == "cancelled"

    def test_pending_to_cancelled(self, db, test_run):
        updated = pipeline_service.update_run_status(
            db=db, run_id=test_run.id, status="cancelled",
        )
        assert updated.status == "cancelled"

    def test_illegal_transition_raises(self, db, test_run):
        with pytest.raises(PipelineStatusTransitionError):
            pipeline_service.update_run_status(
                db=db, run_id=test_run.id, status="completed",
            )

    def test_nonexistent_run_returns_none(self, db):
        result = pipeline_service.update_run_status(
            db=db, run_id=999999, status="running",
        )
        assert result is None


class TestCreateStep:
    def test_creates_step(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="test_step",
        )
        assert step.run_id == test_run.id
        assert step.status == "pending"

    def test_nonexistent_run_raises(self, db):
        with pytest.raises(PipelineStepValidationError):
            pipeline_service.create_step(
                db=db, run_id=999999, step_name="test_step",
            )


class TestUpdateStepStatus:
    def test_pending_to_running(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg",
        )
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="running",
        )
        assert updated.status == "running"
        assert updated.started_at is not None

    def test_running_to_done(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg2",
        )
        pipeline_service.update_step_status(db=db, step_id=step.id, status="running")
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="done",
        )
        assert updated.status == "done"
        assert updated.finished_at is not None

    def test_running_to_degraded(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg3",
        )
        pipeline_service.update_step_status(db=db, step_id=step.id, status="running")
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="degraded",
            degraded=True, retried_count=2,
        )
        assert updated.status == "degraded"
        assert updated.degraded is True
        assert updated.retried_count == 2

    def test_running_to_failed(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg4",
        )
        pipeline_service.update_step_status(db=db, step_id=step.id, status="running")
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="failed", error="timeout",
        )
        assert updated.status == "failed"
        assert updated.error == "timeout"

    def test_failed_to_running_retry(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg5",
        )
        pipeline_service.update_step_status(db=db, step_id=step.id, status="running")
        pipeline_service.update_step_status(db=db, step_id=step.id, status="failed")
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="running",
        )
        assert updated.status == "running"

    def test_pending_to_skipped(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg6",
        )
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="skipped",
        )
        assert updated.status == "skipped"

    def test_illegal_transition_raises(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg7",
        )
        with pytest.raises(PipelineStatusTransitionError):
            pipeline_service.update_step_status(
                db=db, step_id=step.id, status="completed",
            )

    def test_nonexistent_step_returns_none(self, db):
        result = pipeline_service.update_step_status(
            db=db, step_id=999999, status="running",
        )
        assert result is None

    def test_output_artifact_ids_updated(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="sg8",
        )
        pipeline_service.update_step_status(db=db, step_id=step.id, status="running")
        updated = pipeline_service.update_step_status(
            db=db, step_id=step.id, status="done",
            output_artifact_ids=[10, 20],
        )
        assert updated.output_artifact_ids == [10, 20]


class TestCreateArtifact:
    def test_creates_artifact(self, db, test_run):
        artifact = pipeline_service.create_artifact(
            db=db,
            run_id=test_run.id,
            kind="raw_signals",
            content_hash="unique_hash_001",
            payload={"has_prd": True},
            confidence=0.9,
        )
        assert artifact.run_id == test_run.id
        assert artifact.kind == "raw_signals"
        assert artifact.confidence == 0.9

    def test_duplicate_hash_raises(self, db, test_run):
        pipeline_service.create_artifact(
            db=db,
            run_id=test_run.id,
            kind="raw_signals",
            content_hash="dup_hash_001",
        )
        with pytest.raises(DuplicateArtifactHashError):
            pipeline_service.create_artifact(
                db=db,
                run_id=test_run.id,
                kind="raw_signals",
                content_hash="dup_hash_001",
            )

    def test_nonexistent_run_raises(self, db):
        with pytest.raises(PipelineRunValidationError):
            pipeline_service.create_artifact(
                db=db,
                run_id=999999,
                kind="raw_signals",
                content_hash="x",
            )


class TestFindCachedStep:
    def test_cache_hit(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="cached_sg",
            cache_key="cache_key_abc",
        )
        pipeline_service.update_step_status(db=db, step_id=step.id, status="running")
        pipeline_service.update_step_status(db=db, step_id=step.id, status="done")

        found = pipeline_service.find_cached_step(db=db, cache_key="cache_key_abc")
        assert found is not None
        assert found.id == step.id

    def test_cache_miss(self, db):
        found = pipeline_service.find_cached_step(db=db, cache_key="nonexistent_key")
        assert found is None


class TestListRuns:
    def test_returns_runs_for_iteration(self, db, test_iteration):
        pipeline_service.create_run(
            db=db, iteration_id=test_iteration.id,
            input_hash="list_hash_1", pipeline_version="1.0",
        )
        db.flush()
        pipeline_service.create_run(
            db=db, iteration_id=test_iteration.id,
            input_hash="list_hash_2", pipeline_version="1.0",
        )
        db.flush()

        runs = pipeline_service.list_runs(db=db, iteration_id=test_iteration.id)
        assert len(runs) >= 2


class TestGetArtifactByHash:
    def test_found(self, db, test_run):
        pipeline_service.create_artifact(
            db=db, run_id=test_run.id,
            kind="raw_signals", content_hash="find_hash_001",
        )
        found = pipeline_service.get_artifact_by_hash(db=db, content_hash="find_hash_001")
        assert found is not None

    def test_not_found(self, db):
        found = pipeline_service.get_artifact_by_hash(db=db, content_hash="nonexistent")
        assert found is None


class TestIncrementStepRetriedCount:
    def test_increments(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="retry_step",
        )
        pipeline_service.increment_step_retried_count(db=db, step_id=step.id)
        db.refresh(step)
        assert step.retried_count == 1

    def test_nonexistent_step_no_error(self, db):
        pipeline_service.increment_step_retried_count(db=db, step_id=999999)


class TestUpdateStepOutputArtifactIds:
    def test_updates(self, db, test_run):
        step = pipeline_service.create_step(
            db=db, run_id=test_run.id, step_name="output_step",
        )
        pipeline_service.update_step_output_artifact_ids(
            db=db, step_id=step.id, artifact_ids=[1, 2, 3],
        )
        db.refresh(step)
        assert step.output_artifact_ids == [1, 2, 3]

    def test_nonexistent_step_no_error(self, db):
        pipeline_service.update_step_output_artifact_ids(
            db=db, step_id=999999, artifact_ids=[1],
        )


class TestComputeInputHash:
    def test_deterministic(self):
        inp1 = IterationInput(iteration_id=1, kind="prd", content_hash="abc", payload={})
        inp2 = IterationInput(iteration_id=1, kind="testpoint", content_hash="def", payload={})
        h1 = compute_input_hash([inp1, inp2])
        h2 = compute_input_hash([inp2, inp1])
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        inp1 = IterationInput(iteration_id=1, kind="prd", content_hash="abc", payload={})
        inp2 = IterationInput(iteration_id=1, kind="prd", content_hash="xyz", payload={})
        assert compute_input_hash([inp1]) != compute_input_hash([inp2])


class TestComputeCacheKey:
    def test_deterministic(self):
        k1 = compute_cache_key("sg", "1.0", ["h1", "h2"])
        k2 = compute_cache_key("sg", "1.0", ["h2", "h1"])
        assert k1 == k2

    def test_different_step_different_key(self):
        k1 = compute_cache_key("sg", "1.0", ["h1"])
        k2 = compute_cache_key("cg", "1.0", ["h1"])
        assert k1 != k2
