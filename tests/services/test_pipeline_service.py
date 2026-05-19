import pytest
from app.services.pipeline_service._errors import (
    DuplicateArtifactHashError,
    PipelineRunValidationError,
    PipelineStepValidationError,
    PipelineStatusTransitionError,
    PIPELINE_RUN_TRANSITIONS,
    PIPELINE_STEP_TRANSITIONS,
)
from app.services.pipeline_service._run import (
    compute_input_hash,
    create_run,
    get_run,
    list_runs,
    update_run_status,
)
from app.services.pipeline_service._step import (
    compute_cache_key,
    create_step,
    find_cached_step,
    update_step_status,
    increment_step_retried_count,
    update_step_output_artifact_ids,
)
from app.models.enums import PipelineRunStatus, PipelineStepStatus
from app.models.iteration import IterationInput


class TestPipelineErrors:
    def test_duplicate_artifact_hash(self):
        err = DuplicateArtifactHashError("abc123")
        assert "abc123" in str(err)

    def test_run_validation_error(self):
        err = PipelineRunValidationError("不存在")
        assert "不存在" in str(err)

    def test_step_validation_error(self):
        err = PipelineStepValidationError("不存在")
        assert "不存在" in str(err)

    def test_status_transition_error(self):
        err = PipelineStatusTransitionError("Run", "pending", "completed")
        assert "pending" in str(err)
        assert "completed" in str(err)
        assert err.from_status == "pending"
        assert err.to_status == "completed"


class TestPipelineRunTransitions:
    def test_valid_transitions(self):
        assert (PipelineRunStatus.PENDING.value, PipelineRunStatus.RUNNING.value) in PIPELINE_RUN_TRANSITIONS
        assert (PipelineRunStatus.RUNNING.value, PipelineRunStatus.COMPLETED.value) in PIPELINE_RUN_TRANSITIONS
        assert (PipelineRunStatus.RUNNING.value, PipelineRunStatus.FAILED.value) in PIPELINE_RUN_TRANSITIONS

    def test_invalid_transition_not_in_set(self):
        assert (PipelineRunStatus.COMPLETED.value, PipelineRunStatus.RUNNING.value) not in PIPELINE_RUN_TRANSITIONS


class TestPipelineStepTransitions:
    def test_valid_transitions(self):
        assert (PipelineStepStatus.PENDING.value, PipelineStepStatus.RUNNING.value) in PIPELINE_STEP_TRANSITIONS
        assert (PipelineStepStatus.RUNNING.value, PipelineStepStatus.DONE.value) in PIPELINE_STEP_TRANSITIONS

    def test_failed_to_running_allowed(self):
        assert (PipelineStepStatus.FAILED.value, PipelineStepStatus.RUNNING.value) in PIPELINE_STEP_TRANSITIONS


class TestComputeInputHash:
    def test_deterministic(self):
        inputs = [
            IterationInput(kind="xmind", content_hash="h1"),
            IterationInput(kind="ui", content_hash="h2"),
        ]
        h1 = compute_input_hash(inputs)
        h2 = compute_input_hash(inputs)
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        inputs_a = [IterationInput(kind="xmind", content_hash="h1")]
        inputs_b = [IterationInput(kind="xmind", content_hash="h2")]
        assert compute_input_hash(inputs_a) != compute_input_hash(inputs_b)

    def test_order_independent(self):
        inputs_a = [
            IterationInput(kind="xmind", content_hash="h1"),
            IterationInput(kind="ui", content_hash="h2"),
        ]
        inputs_b = [
            IterationInput(kind="ui", content_hash="h2"),
            IterationInput(kind="xmind", content_hash="h1"),
        ]
        assert compute_input_hash(inputs_a) == compute_input_hash(inputs_b)

    def test_empty_list(self):
        h = compute_input_hash([])
        assert isinstance(h, str)
        assert len(h) == 64


class TestComputeCacheKey:
    def test_deterministic(self):
        key1 = compute_cache_key("signal_gatherer", "1.0", ["h1", "h2"])
        key2 = compute_cache_key("signal_gatherer", "1.0", ["h1", "h2"])
        assert key1 == key2

    def test_different_step_name(self):
        key1 = compute_cache_key("step_a", "1.0", ["h1"])
        key2 = compute_cache_key("step_b", "1.0", ["h1"])
        assert key1 != key2

    def test_sorted_hashes(self):
        key1 = compute_cache_key("s", "1.0", ["h2", "h1"])
        key2 = compute_cache_key("s", "1.0", ["h1", "h2"])
        assert key1 == key2

    def test_empty_hashes(self):
        key = compute_cache_key("s", "1.0", [])
        assert isinstance(key, str)


class TestCreateRun:
    def test_nonexistent_iteration(self, db):
        with pytest.raises(PipelineRunValidationError):
            create_run(db, iteration_id=99999, input_hash="abc")


class TestGetRun:
    def test_nonexistent(self, db):
        result = get_run(db, run_id=99999)
        assert result is None


class TestListRuns:
    def test_nonexistent_iteration(self, db):
        runs = list_runs(db, iteration_id=99999)
        assert runs == []


class TestUpdateRunStatus:
    def test_nonexistent(self, db):
        result = update_run_status(db, run_id=99999, status=PipelineRunStatus.RUNNING.value)
        assert result is None


class TestCreateStep:
    def test_nonexistent_run(self, db):
        with pytest.raises(PipelineStepValidationError):
            create_step(db, run_id=99999, step_name="test_step")


class TestFindCachedStep:
    def test_nonexistent(self, db):
        result = find_cached_step(db, cache_key="nonexistent")
        assert result is None


class TestUpdateStepStatus:
    def test_nonexistent(self, db):
        result = update_step_status(db, step_id=99999, status=PipelineStepStatus.RUNNING.value)
        assert result is None


class TestIncrementStepRetriedCount:
    def test_nonexistent(self, db):
        increment_step_retried_count(db, step_id=99999)


class TestUpdateStepOutputArtifactIds:
    def test_nonexistent(self, db):
        update_step_output_artifact_ids(db, step_id=99999, artifact_ids=[1, 2])
