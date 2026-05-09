"""
M1-T09 Pipeline Runner 测试模块

覆盖�?
    - PipelineRunner 正常执行
    - 缓存命中跳过
    - 重试逻辑
    - fallback 降级
    - 预算超限暂停
    - should_run=False 跳过
    - 产物持久�?
    - validate_output 失败
"""
import pytest
from typing import ClassVar, List, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner, MAX_RETRIES
from app.models.pipeline import PipelineRun
from app.services import pipeline_service


class AlwaysRunStep:
    name: ClassVar[str] = "always_run"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["test_artifact"]

    def should_run(self, ctx):
        return True

    def cache_key(self, ctx):
        return f"{self.name}:{self.version}:default"

    def execute(self, ctx):
        return StepResult(
            success=True,
            artifact_payload={"data": "hello"},
            artifact_kind="test_artifact",
            artifact_confidence=0.95,
        )

    def validate_output(self, payload):
        return isinstance(payload, dict) and "data" in payload

    def fallback(self, ctx, error):
        return StepResult(
            success=True,
            artifact_payload={"data": "fallback"},
            artifact_kind="test_artifact",
            degraded=True,
        )


class SkipStep:
    name: ClassVar[str] = "skip_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = []

    def should_run(self, ctx):
        return False

    def cache_key(self, ctx):
        return f"{self.name}:{self.version}:default"

    def execute(self, ctx):
        return StepResult(success=True)

    def validate_output(self, payload):
        return True

    def fallback(self, ctx, error):
        return None


class FailStep:
    name: ClassVar[str] = "fail_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = []

    def should_run(self, ctx):
        return True

    def cache_key(self, ctx):
        return f"{self.name}:{self.version}:default"

    def execute(self, ctx):
        raise RuntimeError("Step execution failed")

    def validate_output(self, payload):
        return True

    def fallback(self, ctx, error):
        return StepResult(
            success=True,
            artifact_payload={"data": "degraded"},
            artifact_kind="test_artifact",
            degraded=True,
        )


class NoFallbackStep:
    name: ClassVar[str] = "no_fallback_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = []

    def should_run(self, ctx):
        return True

    def cache_key(self, ctx):
        return f"{self.name}:{self.version}:default"

    def execute(self, ctx):
        raise RuntimeError("Unrecoverable failure")

    def validate_output(self, payload):
        return True

    def fallback(self, ctx, error):
        return None


class InvalidOutputStep:
    name: ClassVar[str] = "invalid_output_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["bad_artifact"]

    def should_run(self, ctx):
        return True

    def cache_key(self, ctx):
        return f"{self.name}:{self.version}:default"

    def execute(self, ctx):
        return StepResult(
            success=True,
            artifact_payload={"missing_key": True},
            artifact_kind="bad_artifact",
        )

    def validate_output(self, payload):
        return False

    def fallback(self, ctx, error):
        return None


class BudgetExhaustedStep:
    name: ClassVar[str] = "budget_exhausted_step"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = []

    def should_run(self, ctx):
        return True

    def cache_key(self, ctx):
        return f"{self.name}:{self.version}:default"

    def execute(self, ctx):
        return StepResult(success=True)

    def validate_output(self, payload):
        return True

    def fallback(self, ctx, error):
        return None


@pytest.fixture
def pipeline_run(db, testProject):
    from app.models.iteration import Iteration
    iteration = Iteration(
        project_id=testProject.id,
        name="test_iteration",
        status="in_pipeline",
    )
    db.add(iteration)
    db.flush()

    run = pipeline_service.create_run(
        db=db,
        iteration_id=iteration.id,
        input_hash="test_hash_123",
        pipeline_version="1.0",
    )
    db.flush()
    return run


@pytest.fixture
def make_ctx(db, pipeline_run):
    from app.ai.mock_client import MockAIClient

    def _make():
        return PipelineContext(
            db=db,
            ai_client=MockAIClient(),
            run=pipeline_run,
            iteration_id=pipeline_run.iteration_id,
            user_id=1,
        )
    return _make


class TestPipelineRunnerNormal:
    def test_single_step_success(self, db, make_ctx):
        runner = PipelineRunner("test_pipeline", [AlwaysRunStep])
        ctx = make_ctx()
        runner.run(ctx)
        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

    def test_skip_step(self, db, make_ctx):
        runner = PipelineRunner("test_pipeline", [SkipStep])
        ctx = make_ctx()
        runner.run(ctx)
        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

    def test_artifact_persisted(self, db, make_ctx):
        runner = PipelineRunner("test_pipeline", [AlwaysRunStep])
        ctx = make_ctx()
        runner.run(ctx)
        artifact = ctx.get_artifact("test_artifact")
        assert artifact is not None
        assert artifact["data"] == "hello"


class TestPipelineRunnerRetry:
    def test_fail_step_uses_fallback(self, db, make_ctx):
        runner = PipelineRunner("test_pipeline", [FailStep])
        ctx = make_ctx()
        runner.run(ctx)
        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

    def test_no_fallback_step_fails_pipeline(self, db, make_ctx):
        runner = PipelineRunner("test_pipeline", [NoFallbackStep])
        ctx = make_ctx()
        runner.run(ctx)
        db.refresh(ctx.run)
        assert ctx.run.status == "failed"

    def test_max_retries_is_2(self):
        assert MAX_RETRIES == 2


class TestPipelineRunnerCache:
    def test_cache_hit_skips_execute(self, db, make_ctx):
        ctx = make_ctx()
        cache_key = f"always_run:1.0:default"
        step_record = pipeline_service.create_step(
            db=db,
            run_id=ctx.run.id,
            step_name="always_run",
            step_version="1.0",
            cache_key=cache_key,
        )
        pipeline_service.update_step_status(db=db, step_id=step_record.id, status="done")

        runner = PipelineRunner("test_pipeline", [AlwaysRunStep])
        runner.run(ctx)
        db.refresh(ctx.run)
        assert ctx.run.status == "completed"


class TestPipelineRunnerBudget:
    def test_budget_exceeded_pauses(self, db, testProject):
        from app.models.iteration import Iteration
        from app.ai.mock_client import MockAIClient
        from app.ai.call_log import AICallLog
        from app.core.config import settings

        iteration = Iteration(
            project_id=testProject.id,
            name="budget_test_iteration",
            status="in_pipeline",
        )
        db.add(iteration)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="budget_test_hash",
            pipeline_version="1.0",
        )
        db.flush()

        budget_limit = getattr(settings, "AI_TOKEN_BUDGET_PER_RUN", 500000)
        for _ in range(3):
            log_entry = AICallLog(
                run_id=run.id,
                step_name="budget_exhausted_step",
                model="test-model",
                prompt_tokens=budget_limit,
                completion_tokens=0,
                cost_usd=0.0,
                latency_ms=0,
                status="success",
            )
            db.add(log_entry)
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=MockAIClient(),
            run=run,
            iteration_id=iteration.id,
            user_id=1,
        )

        runner = PipelineRunner("test_pipeline", [BudgetExhaustedStep])
        runner.run(ctx)
        db.refresh(run)
        assert run.status == "waiting_for_user"


class TestPipelineRunnerValidation:
    def test_invalid_output_triggers_fallback(self, db, make_ctx):
        runner = PipelineRunner("test_pipeline", [InvalidOutputStep])
        ctx = make_ctx()
        runner.run(ctx)
        db.refresh(ctx.run)
        assert ctx.run.status == "failed"
