"""
M1-T07 PipelineService 单元测试

覆盖范围：
1. compute_input_hash / compute_cache_key 工具函数
2. create_run 幂等（相同 input_hash + pipeline_version 返回旧 run）
3. create_run pipeline_version 升级强制重跑
4. create_run iteration_id 存在性校验
5. get_run / list_runs 查询
6. update_run_status 状态迁移校验 + 时间戳
7. create_step run_id 存在性校验
8. find_cached_step 缓存命中/失效
9. update_step_status 状态迁移校验 + 重试/降级
10. create_artifact 唯一约束 + run_id 校验
11. get_artifact_by_hash
12. 枚举值正确性
"""
import pytest

from app.models.enums import PipelineRunStatus, PipelineStepStatus
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.models.iteration import Iteration, IterationInput
from app.models.project import Project
from app.models.user import User
from app.services.pipeline_service import (
    compute_input_hash,
    compute_cache_key,
    create_run,
    get_run,
    list_runs,
    update_run_status,
    create_step,
    find_cached_step,
    update_step_status,
    create_artifact,
    get_artifact_by_hash,
    DuplicateArtifactHashError,
    PipelineRunValidationError,
    PipelineStepValidationError,
    PipelineStatusTransitionError,
)


# ==================== Fixtures ====================

@pytest.fixture
def test_user(db):
    user = User(username="pipe_test_user", email="pipe_test@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="Pipeline测试项目", user_id=test_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    return project


@pytest.fixture
def test_iteration(db, test_project):
    it = Iteration(project_id=test_project.id, name="Sprint 1", version="v1.0")
    db.add(it)
    db.flush()
    db.refresh(it)
    return it


# ==================== 工具函数 ====================

class TestHashFunctions:
    """哈希计算工具函数测试"""

    def test_compute_input_hash(self, db, test_iteration):
        inp1 = IterationInput(iteration_id=test_iteration.id, kind="prd",
                              content_hash="h1")
        inp2 = IterationInput(iteration_id=test_iteration.id, kind="xmind",
                              content_hash="h2")
        db.add_all([inp1, inp2])
        db.flush()

        result = compute_input_hash([inp1, inp2])
        assert len(result) == 64  # SHA-256 hex

    def test_compute_input_hash_deterministic(self, db, test_iteration):
        inp1 = IterationInput(iteration_id=test_iteration.id, kind="prd",
                              content_hash="h1")
        inp2 = IterationInput(iteration_id=test_iteration.id, kind="xmind",
                              content_hash="h2")
        db.add_all([inp1, inp2])
        db.flush()

        h1 = compute_input_hash([inp1, inp2])
        h2 = compute_input_hash([inp2, inp1])  # 顺序无关
        assert h1 == h2

    def test_compute_cache_key(self):
        key = compute_cache_key("signal_gatherer", "1.0", ["h1", "h2"])
        assert len(key) == 64

    def test_compute_cache_key_deterministic(self):
        k1 = compute_cache_key("step", "1.0", ["h2", "h1"])
        k2 = compute_cache_key("step", "1.0", ["h1", "h2"])
        assert k1 == k2

    def test_compute_cache_key_different_step(self):
        k1 = compute_cache_key("step_a", "1.0", ["h1"])
        k2 = compute_cache_key("step_b", "1.0", ["h1"])
        assert k1 != k2


# ==================== PipelineRun ====================

class TestPipelineRun:
    """PipelineRun CRUD + 幂等 + 校验测试"""

    def test_create_run(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "hash1")
        assert run.id is not None
        assert run.status == PipelineRunStatus.PENDING.value
        assert run.input_hash == "hash1"

    def test_create_run_idempotent(self, db, test_iteration):
        run1 = create_run(db, test_iteration.id, "same_hash")
        # pending → running → completed
        update_run_status(db, run1.id, PipelineRunStatus.RUNNING.value)
        update_run_status(db, run1.id, PipelineRunStatus.COMPLETED.value)
        run2 = create_run(db, test_iteration.id, "same_hash")
        assert run2.id == run1.id  # 返回已有 run

    def test_create_run_pipeline_version_upgrade(self, db, test_iteration):
        """pipeline_version 升级后应强制重跑"""
        run1 = create_run(db, test_iteration.id, "same_hash", pipeline_version="1.0")
        update_run_status(db, run1.id, PipelineRunStatus.RUNNING.value)
        update_run_status(db, run1.id, PipelineRunStatus.COMPLETED.value)
        # 版本升级 → 新 run
        run2 = create_run(db, test_iteration.id, "same_hash", pipeline_version="2.0")
        assert run2.id != run1.id

    def test_create_run_different_hash(self, db, test_iteration):
        run1 = create_run(db, test_iteration.id, "hash_a")
        run2 = create_run(db, test_iteration.id, "hash_b")
        assert run1.id != run2.id

    def test_create_run_failed_not_cached(self, db, test_iteration):
        """失败的 run 不应被缓存复用"""
        run1 = create_run(db, test_iteration.id, "fail_hash")
        update_run_status(db, run1.id, PipelineRunStatus.RUNNING.value)
        update_run_status(db, run1.id, PipelineRunStatus.FAILED.value, error="boom")
        run2 = create_run(db, test_iteration.id, "fail_hash")
        assert run2.id != run1.id  # 失败 run 不复用

    def test_create_run_iteration_not_found(self, db):
        with pytest.raises(PipelineRunValidationError, match="不存在"):
            create_run(db, 99999, "hash1")

    def test_get_run(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "hash1")
        found = get_run(db, run.id)
        assert found is not None
        assert found.id == run.id

    def test_get_run_not_found(self, db):
        assert get_run(db, 99999) is None

    def test_list_runs(self, db, test_iteration):
        create_run(db, test_iteration.id, "h1")
        create_run(db, test_iteration.id, "h2")
        runs = list_runs(db, test_iteration.id)
        assert len(runs) >= 2

    def test_list_runs_pagination(self, db, test_iteration):
        for i in range(5):
            create_run(db, test_iteration.id, f"page_h_{i}")
        page1 = list_runs(db, test_iteration.id, skip=0, limit=2)
        page2 = list_runs(db, test_iteration.id, skip=2, limit=2)
        assert len(page1) == 2
        assert len(page2) == 2

    # --- 状态迁移 ---

    def test_run_pending_to_running(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        result = update_run_status(db, run.id, PipelineRunStatus.RUNNING.value)
        assert result.status == PipelineRunStatus.RUNNING.value
        assert result.started_at is not None

    def test_run_running_to_completed(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        update_run_status(db, run.id, PipelineRunStatus.RUNNING.value)
        result = update_run_status(db, run.id, PipelineRunStatus.COMPLETED.value)
        assert result.status == PipelineRunStatus.COMPLETED.value
        assert result.finished_at is not None

    def test_run_running_to_failed(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        update_run_status(db, run.id, PipelineRunStatus.RUNNING.value)
        result = update_run_status(db, run.id, PipelineRunStatus.FAILED.value, error="timeout")
        assert result.error == "timeout"
        assert result.finished_at is not None

    def test_run_running_to_waiting_for_user(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        update_run_status(db, run.id, PipelineRunStatus.RUNNING.value)
        result = update_run_status(db, run.id, PipelineRunStatus.WAITING_FOR_USER.value)
        assert result.status == PipelineRunStatus.WAITING_FOR_USER.value

    def test_run_pending_to_cancelled(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        result = update_run_status(db, run.id, PipelineRunStatus.CANCELLED.value)
        assert result.status == PipelineRunStatus.CANCELLED.value

    def test_run_illegal_pending_to_completed(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        with pytest.raises(PipelineStatusTransitionError):
            update_run_status(db, run.id, PipelineRunStatus.COMPLETED.value)

    def test_transition_error_without_detail(self):
        """PipelineStatusTransitionError 无 detail 时消息格式"""
        err = PipelineStatusTransitionError("TestEntity", "a", "b")
        assert "TestEntity" in str(err)
        assert "a → b" in str(err)
        assert "—" not in str(err)

    def test_run_illegal_completed_to_running(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        update_run_status(db, run.id, PipelineRunStatus.RUNNING.value)
        update_run_status(db, run.id, PipelineRunStatus.COMPLETED.value)
        with pytest.raises(PipelineStatusTransitionError):
            update_run_status(db, run.id, PipelineRunStatus.RUNNING.value)

    def test_update_run_not_found(self, db):
        assert update_run_status(db, 99999, PipelineRunStatus.RUNNING.value) is None


# ==================== PipelineStep ====================

class TestPipelineStep:
    """PipelineStep CRUD + 缓存 + 校验测试"""

    def test_create_step(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "signal_gatherer", cache_key="ck1")
        assert step.id is not None
        assert step.step_name == "signal_gatherer"
        assert step.status == PipelineStepStatus.PENDING.value
        assert step.cache_key == "ck1"

    def test_create_step_run_not_found(self, db):
        with pytest.raises(PipelineStepValidationError, match="不存在"):
            create_step(db, 99999, "step1")

    def test_find_cached_step_hit(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "signal_gatherer", cache_key="cache_me")
        update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        update_step_status(db, step.id, PipelineStepStatus.DONE.value,
                           output_artifact_ids=[1])

        cached = find_cached_step(db, "cache_me")
        assert cached is not None
        assert cached.id == step.id

    def test_find_cached_step_miss(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "signal_gatherer", cache_key="no_cache")
        # step 还是 pending，不是 done
        cached = find_cached_step(db, "no_cache")
        assert cached is None

    def test_find_cached_step_failed_not_cached(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "signal_gatherer", cache_key="failed_cache")
        update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        update_step_status(db, step.id, PipelineStepStatus.FAILED.value, error="boom")

        cached = find_cached_step(db, "failed_cache")
        assert cached is None  # 失败 step 不缓存

    # --- 状态迁移 ---

    def test_step_pending_to_running(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        result = update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        assert result.status == PipelineStepStatus.RUNNING.value
        assert result.started_at is not None

    def test_step_running_to_done(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        result = update_step_status(db, step.id, PipelineStepStatus.DONE.value,
                                    output_artifact_ids=[1, 2])
        assert result.status == PipelineStepStatus.DONE.value
        assert result.output_artifact_ids == [1, 2]
        assert result.finished_at is not None

    def test_step_running_to_degraded(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        result = update_step_status(db, step.id, PipelineStepStatus.DEGRADED.value,
                                    degraded=True, retried_count=3)
        assert result.degraded is True
        assert result.retried_count == 3

    def test_step_pending_to_skipped(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        result = update_step_status(db, step.id, PipelineStepStatus.SKIPPED.value)
        assert result.status == PipelineStepStatus.SKIPPED.value
        assert result.finished_at is not None

    def test_step_failed_retry(self, db, test_iteration):
        """failed → running 重试"""
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        update_step_status(db, step.id, PipelineStepStatus.FAILED.value, error="boom")
        result = update_step_status(db, step.id, PipelineStepStatus.RUNNING.value,
                                    retried_count=1)
        assert result.status == PipelineStepStatus.RUNNING.value
        assert result.retried_count == 1

    def test_step_illegal_pending_to_done(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        with pytest.raises(PipelineStatusTransitionError):
            update_step_status(db, step.id, PipelineStepStatus.DONE.value)

    def test_step_illegal_done_to_running(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        step = create_step(db, run.id, "step1")
        update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)
        update_step_status(db, step.id, PipelineStepStatus.DONE.value)
        with pytest.raises(PipelineStatusTransitionError):
            update_step_status(db, step.id, PipelineStepStatus.RUNNING.value)

    def test_update_step_not_found(self, db):
        assert update_step_status(db, 99999, PipelineStepStatus.DONE.value) is None


# ==================== Artifact ====================

class TestArtifact:
    """Artifact CRUD + 唯一约束 + 校验测试"""

    def test_create_artifact(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        art = create_artifact(db, run.id, "test_points", "art_hash_1",
                              payload={"items": [1, 2]}, confidence=0.85)
        assert art.id is not None
        assert art.kind == "test_points"
        assert art.confidence == 0.85
        assert art.content_hash == "art_hash_1"

    def test_create_artifact_duplicate_hash(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        create_artifact(db, run.id, "test_points", "dup_hash")
        with pytest.raises(DuplicateArtifactHashError, match="dup_hash"):
            create_artifact(db, run.id, "test_points", "dup_hash")

    def test_create_artifact_run_not_found(self, db):
        with pytest.raises(PipelineRunValidationError, match="不存在"):
            create_artifact(db, 99999, "test_points", "art_hash")

    def test_get_artifact_by_hash(self, db, test_iteration):
        run = create_run(db, test_iteration.id, "h1")
        create_artifact(db, run.id, "test_points", "find_me",
                        payload={"x": 1})
        found = get_artifact_by_hash(db, "find_me")
        assert found is not None
        assert found.kind == "test_points"

    def test_get_artifact_by_hash_not_found(self, db):
        assert get_artifact_by_hash(db, "nonexistent") is None


# ==================== Enums ====================

class TestEnums:
    """枚举值正确性测试"""

    def test_pipeline_run_status_values(self):
        assert PipelineRunStatus.PENDING.value == "pending"
        assert PipelineRunStatus.RUNNING.value == "running"
        assert PipelineRunStatus.WAITING_FOR_USER.value == "waiting_for_user"
        assert PipelineRunStatus.COMPLETED.value == "completed"
        assert PipelineRunStatus.FAILED.value == "failed"
        assert PipelineRunStatus.CANCELLED.value == "cancelled"

    def test_pipeline_step_status_values(self):
        assert PipelineStepStatus.PENDING.value == "pending"
        assert PipelineStepStatus.RUNNING.value == "running"
        assert PipelineStepStatus.DONE.value == "done"
        assert PipelineStepStatus.FAILED.value == "failed"
        assert PipelineStepStatus.SKIPPED.value == "skipped"
        assert PipelineStepStatus.DEGRADED.value == "degraded"
