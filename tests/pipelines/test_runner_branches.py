"""Pipeline Runner 分支覆盖测试

覆盖范围:
    - should_run=False 跳过 Step
    - check_budget=False 预算超限暂停
    - pause_for_confirmation=True 等待用户确认
    - 缓存命中 + output_artifact_ids 关联产物
    - validate_output=False 输出校验失败触发重试
    - 重试耗尽 + fallback 降级
    - 重试耗尽 + fallback 返回 None → Pipeline 失败
    - _persist_artifact 正常路径

使用自定义 StubStep 替代真实 Step，精确控制每个分支。
"""
import json
import pytest
from typing import Any, ClassVar, Dict, List, Optional
from unittest.mock import patch

from app.models.iteration import Iteration, IterationInput
from app.models.test_point import TestPoint
from app.ai.mock_client import MockAIClient
from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.services import pipeline_service


class SkipStep(PipelineStep):
    name: ClassVar[str] = "skip_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["skipped_output"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return False

    def cache_key(self, ctx: PipelineContext) -> str:
        return "skip_step:v1:[]"

    def execute(self, ctx: PipelineContext) -> StepResult:
        return StepResult(success=True, artifact_payload={"data": "skip"}, artifact_kind="skipped_output")

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return True

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return None


class PauseStep(PipelineStep):
    name: ClassVar[str] = "pause_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["pause_output"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        return "pause_step:v1:[]"

    def execute(self, ctx: PipelineContext) -> StepResult:
        return StepResult(
            success=True,
            artifact_payload={"data": "pause"},
            artifact_kind="pause_output",
            pause_for_confirmation=True,
            confirmation_reason="需要用户确认",
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return True

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return None


class FailStep(PipelineStep):
    name: ClassVar[str] = "fail_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = []

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        return f"fail_step:v1:{id(self)}"

    def execute(self, ctx: PipelineContext) -> StepResult:
        raise RuntimeError("Step execution failed")

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return True

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return None


class FallbackStep(PipelineStep):
    name: ClassVar[str] = "fallback_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["fallback_output"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        return f"fallback_step:v1:{id(self)}"

    def execute(self, ctx: PipelineContext) -> StepResult:
        raise RuntimeError("Step always fails")

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return True

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=True,
            artifact_payload={"data": "fallback"},
            artifact_kind="fallback_output",
            degraded=True,
        )


class InvalidOutputStep(PipelineStep):
    name: ClassVar[str] = "invalid_output_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["invalid_output"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        return f"invalid_output_step:v1:{id(self)}"

    def execute(self, ctx: PipelineContext) -> StepResult:
        return StepResult(
            success=True,
            artifact_payload={"invalid": True},
            artifact_kind="invalid_output",
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return False

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=True,
            artifact_payload={"data": "fallback_after_invalid"},
            artifact_kind="invalid_output",
            degraded=True,
        )


class NormalStep(PipelineStep):
    name: ClassVar[str] = "normal_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["normal_output"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        return "normal_step:v1:deterministic"

    def execute(self, ctx: PipelineContext) -> StepResult:
        return StepResult(
            success=True,
            artifact_payload={"data": "normal"},
            artifact_kind="normal_output",
            artifact_confidence=0.95,
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return True

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return None


@pytest.fixture
def mock_ai():
    return MockAIClient()


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="runner_branch_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


def _make_ctx(db, mock_ai, iteration):
    run = pipeline_service.create_run(
        db=db,
        iteration_id=iteration.id,
        input_hash=f"runner_branch_{iteration.id}",
        pipeline_version="1.0",
    )
    db.flush()
    return PipelineContext(
        db=db,
        ai_client=mock_ai,
        run=run,
        iteration_id=iteration.id,
        user_id=1,
    )


class TestStepSkipped:
    def test_should_run_false_skips_step(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("skip_pipeline", [SkipStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

        step_record = ctx.get_step_record("skip_step")
        assert step_record is None


class TestBudgetExceeded:
    def test_budget_exceeded_pauses_pipeline(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        with patch.object(ctx, "check_budget", return_value=False):
            runner = PipelineRunner("budget_pipeline", [NormalStep])
            runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "waiting_for_user"
        assert "Token budget exceeded" in (ctx.run.error or "")


class TestPauseForConfirmation:
    def test_pause_for_confirmation_stops_pipeline(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("pause_pipeline", [PauseStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "waiting_for_user"


class TestRetryExhausted:
    def test_all_retries_fail_no_fallback(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("fail_pipeline", [FailStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "failed"

        step_record = ctx.get_step_record("fail_step")
        assert step_record is not None
        assert step_record.retried_count >= 1

    def test_all_retries_fail_with_fallback(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("fallback_pipeline", [FallbackStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

        step_record = ctx.get_step_record("fallback_step")
        assert step_record is not None
        assert step_record.degraded is True


class TestInvalidOutput:
    def test_invalid_output_triggers_retry_and_fallback(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("invalid_output_pipeline", [InvalidOutputStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

        step_record = ctx.get_step_record("invalid_output_step")
        assert step_record is not None
        assert step_record.degraded is True


class TestCacheHitWithArtifacts:
    def test_cache_hit_restores_artifacts(self, db, test_iteration, mock_ai):
        ctx1 = _make_ctx(db, mock_ai, test_iteration)
        runner1 = PipelineRunner("cache_pipeline", [NormalStep])
        runner1.run(ctx1)

        db.refresh(ctx1.run)
        assert ctx1.run.status == "completed"

        step_record = ctx1.get_step_record("normal_step")
        assert step_record is not None
        assert step_record.output_artifact_ids is not None
        assert len(step_record.output_artifact_ids) >= 1

        run2 = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash=f"cache_hit_hash_{test_iteration.id}",
            pipeline_version="1.0",
        )
        db.flush()

        ctx2 = PipelineContext(
            db=db,
            ai_client=mock_ai,
            run=run2,
            iteration_id=test_iteration.id,
            user_id=1,
        )

        runner2 = PipelineRunner("cache_hit_pipeline", [NormalStep])
        runner2.run(ctx2)

        db.refresh(ctx2.run)
        assert ctx2.run.status == "completed"


class TestPersistArtifact:
    def test_normal_step_persists_artifact(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("persist_pipeline", [NormalStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

        step_record = ctx.get_step_record("normal_step")
        assert step_record is not None
        assert step_record.output_artifact_ids is not None
        assert len(step_record.output_artifact_ids) >= 1

        artifact_id = step_record.output_artifact_ids[0]
        from app.models.pipeline import Artifact
        artifact = db.get(Artifact, artifact_id)
        assert artifact is not None
        assert artifact.kind == "normal_output"
        assert artifact.confidence == 0.95


class TestMixedSteps:
    def test_skip_then_normal_completes(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("mixed_pipeline", [SkipStep, NormalStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

        assert ctx.get_step_record("skip_step") is None
        assert ctx.get_step_record("normal_step") is not None

    def test_fail_stops_subsequent_steps(self, db, test_iteration, mock_ai):
        ctx = _make_ctx(db, mock_ai, test_iteration)
        runner = PipelineRunner("fail_stop_pipeline", [FailStep, NormalStep])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "failed"
        assert ctx.get_step_record("fail_step") is not None
        assert ctx.get_step_record("normal_step") is None
