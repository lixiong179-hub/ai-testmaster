"""M2-T02 HistoryFingerprint Step 单元测试

覆盖�?
    - should_run 条件判断
    - execute 正常采集指纹
    - execute 无历史用例（空项目）
    - execute 缺少 raw_signals 产物
    - cache_key 确定�?
    - validate_output 校验
    - fallback 降级
    - 过期 summary 增量重算
    - summary 覆盖率与置信度计�?
    - _compute_fingerprint_confidence 边界�?

使用真实 MySQL 数据�?+ MockAIClient�?
"""
import pytest

from app.pipelines.steps.history_fingerprint import (
    HistoryFingerprint,
    _compute_fingerprint_confidence,
    _load_fingerprints,
    _detect_stale_summaries,
    _incremental_backfill,
)
from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration
from app.models.test_case import TestCase
from app.models.pipeline import PipelineRun, Artifact
from app.services import pipeline_service
from app.pipelines.context import PipelineContext


@pytest.fixture
def mock_ai():
    client = MockAIClient()
    client.set_response(
        "history_fingerprint_backfill",
        "这是增量回填生成的摘�?,
    )
    return client


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="fingerprint_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def make_ctx(db, mock_ai, test_iteration):
    def _make_ctx(raw_signals_payload=None):
        run = pipeline_service.create_run(
            db=db,
            iteration_id=test_iteration.id,
            input_hash="fingerprint_test_hash",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=mock_ai,
            run=run,
            iteration_id=test_iteration.id,
            user_id=1,
        )

        if raw_signals_payload is not None:
            artifact = Artifact(
                run_id=run.id,
                kind="raw_signals",
                schema_version="1.0",
                payload=raw_signals_payload,
                content_hash="test_raw_signals",
            )
            db.add(artifact)
            db.flush()
            ctx.set_artifact("raw_signals", artifact)

        return ctx

    return _make_ctx


def _make_raw_signals(project_id: int, **overrides) -> dict:
    payload = {
        "iteration_id": 1,
        "project_id": project_id,
        "prd_content": "测试PRD",
        "test_points": [],
        "has_ui": False,
        "has_prd": True,
        "has_testpoints": False,
    }
    payload.update(overrides)
    return payload


class TestHistoryFingerprintShouldRun:
    def test_should_run_with_raw_signals(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        assert step.should_run(ctx) is True

    def test_should_not_run_without_raw_signals(self, make_ctx):
        ctx = make_ctx()
        step = HistoryFingerprint()
        assert step.should_run(ctx) is False

    def test_should_not_run_without_project_id(self, make_ctx):
        ctx = make_ctx(raw_signals_payload={"iteration_id": 1})
        step = HistoryFingerprint()
        assert step.should_run(ctx) is False


class TestHistoryFingerprintExecute:
    def test_execute_with_existing_cases(self, db, make_ctx, test_iteration):
        case = TestCase(
            case_no="FP-001",
            project_id=test_iteration.project_id,
            module="用户管理",
            title="登录验证",
            precondition="�?,
            steps_json=[{"step": "输入账号密码", "action": "点击登录"}],
            expected_result="登录成功",
            priority=1,
            case_type="functional",
            lifecycle_status="active",
            summary="验证用户登录功能",
            summary_version=1,
            summary_model_version="mock-model",
        )
        db.add(case)
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "history_fingerprints"
        assert result.artifact_payload is not None
        assert result.artifact_payload["total_count"] >= 1
        assert result.artifact_payload["project_id"] == test_iteration.project_id
        fps = result.artifact_payload["fingerprints"]
        assert any(fp["case_id"] == case.id for fp in fps)

    def test_execute_empty_project(self, db, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_payload["total_count"] >= 0
        assert isinstance(result.artifact_payload["fingerprints"], list)

    def test_execute_missing_raw_signals(self, make_ctx):
        ctx = make_ctx()
        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is False
        assert "raw_signals" in result.error

    def test_execute_missing_project_id(self, make_ctx):
        ctx = make_ctx(raw_signals_payload={"iteration_id": 1})
        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is False
        assert "project_id" in result.error

    def test_execute_excludes_archived_cases(self, db, make_ctx, test_iteration):
        case_active = TestCase(
            case_no="FP-ACT",
            project_id=test_iteration.project_id,
            module="模块A",
            title="活跃用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
        )
        case_archived = TestCase(
            case_no="FP-ARC",
            project_id=test_iteration.project_id,
            module="模块A",
            title="已归档用�?,
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=3,
            case_type="functional",
            lifecycle_status="archived",
        )
        db.add_all([case_active, case_archived])
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is True
        fps = result.artifact_payload["fingerprints"]
        case_ids = [fp["case_id"] for fp in fps]
        assert case_active.id in case_ids
        assert case_archived.id not in case_ids


class TestHistoryFingerprintCacheKey:
    def test_cache_key_deterministic(self, make_ctx, test_iteration):
        payload = _make_raw_signals(test_iteration.project_id)
        ctx = make_ctx(raw_signals_payload=payload)
        step = HistoryFingerprint()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64

    def test_cache_key_empty_project(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        key = step.cache_key(ctx)
        assert len(key) == 64

    def test_cache_key_without_raw_signals(self, make_ctx):
        ctx = make_ctx()
        step = HistoryFingerprint()
        key = step.cache_key(ctx)
        assert key == ""


class TestHistoryFingerprintValidateOutput:
    def test_valid_payload(self):
        step = HistoryFingerprint()
        payload = {
            "project_id": 1,
            "fingerprints": [],
            "total_count": 0,
            "stale_backfilled_count": 0,
        }
        assert step.validate_output(payload) is True

    def test_missing_required_field(self):
        step = HistoryFingerprint()
        assert step.validate_output({"project_id": 1}) is False
        assert step.validate_output({"fingerprints": []}) is False
        assert step.validate_output({"project_id": 1, "fingerprints": [], "total_count": 0}) is False


class TestHistoryFingerprintFallback:
    def test_fallback_returns_degraded_result(self):
        step = HistoryFingerprint()
        result = step.fallback(None, RuntimeError("test error"))
        assert result is not None
        assert result.degraded is True
        assert result.success is True
        assert result.artifact_kind == "history_fingerprints"
        assert result.artifact_payload["total_count"] == 0

    def test_fallback_with_raw_signals(self, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result is not None
        assert result.artifact_payload["project_id"] == test_iteration.project_id


class TestIncrementalBackfill:
    def test_stale_summary_triggers_backfill(self, db, make_ctx, mock_ai, test_iteration):
        case = TestCase(
            case_no="FP-STALE",
            project_id=test_iteration.project_id,
            module="模块B",
            title="过期摘要用例",
            precondition="�?,
            steps_json=[{"step": "步骤1"}],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="旧摘�?,
            summary_version=1,
            summary_model_version="old-model-v1",
        )
        db.add(case)
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_payload["stale_backfilled_count"] >= 1

    def test_no_stale_summary_zero_backfill(self, db, testProject, mock_ai):
        iteration = Iteration(
            project_id=testProject.id,
            name="fingerprint_fresh_iter",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        case = TestCase(
            case_no="FP-FRESH-NOBACKFILL",
            project_id=testProject.id,
            module="模块C",
            title="新鲜摘要用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="最新摘�?,
            summary_version=1,
            summary_model_version="mock-model",
        )
        db.add(case)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="fingerprint_fresh_hash",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=mock_ai,
            run=run,
            iteration_id=iteration.id,
            user_id=1,
        )

        raw_signals = _make_raw_signals(testProject.id)
        artifact = Artifact(
            run_id=run.id,
            kind="raw_signals",
            schema_version="1.0",
            payload=raw_signals,
            content_hash="test_raw_signals_fresh",
        )
        db.add(artifact)
        db.flush()
        ctx.set_artifact("raw_signals", artifact)

        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is True
        db.refresh(case)
        assert case.summary_model_version == "mock-model"
        assert case.summary_version == 1


class TestComputeFingerprintConfidence:
    def test_empty_fingerprints(self):
        assert _compute_fingerprint_confidence([]) == 0.0

    def test_full_coverage(self):
        fps = [
            {"summary": "摘要1"},
            {"summary": "摘要2"},
        ]
        assert _compute_fingerprint_confidence(fps) == 1.0

    def test_half_coverage(self):
        fps = [
            {"summary": "摘要1"},
            {"summary": ""},
        ]
        assert _compute_fingerprint_confidence(fps) == 0.8

    def test_low_coverage(self):
        fps = [
            {"summary": ""},
            {"summary": ""},
            {"summary": "仅有1�?},
        ]
        assert _compute_fingerprint_confidence(fps) == 0.5

    def test_no_summary_at_all(self):
        fps = [
            {"summary": ""},
            {"summary": None},
        ]
        assert _compute_fingerprint_confidence(fps) == 0.5


class TestLoadFingerprints:
    def test_loads_correct_fields(self, db, make_ctx, test_iteration):
        case = TestCase(
            case_no="FP-FIELD",
            project_id=test_iteration.project_id,
            module="模块D",
            title="字段验证用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=1,
            case_type="functional",
            lifecycle_status="active",
            summary="字段摘要",
            summary_version=2,
            summary_model_version="mock-v2",
        )
        db.add(case)
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        fps = _load_fingerprints(ctx, test_iteration.project_id)

        assert len(fps) >= 1
        fp = next(f for f in fps if f["case_id"] == case.id)
        assert fp["title"] == "字段验证用例"
        assert fp["module"] == "模块D"
        assert fp["summary"] == "字段摘要"
        assert fp["summary_version"] == 2
        assert fp["summary_model_version"] == "mock-v2"
        assert fp["lifecycle_status"] == "active"
        assert fp["priority"] == 1


class TestDetectStaleSummaries:
    def test_counts_stale_only(self, db, testProject, mock_ai):
        iteration = Iteration(
            project_id=testProject.id,
            name="fingerprint_stale_det_iter",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        stale_case = TestCase(
            case_no="FP-STALE-DET",
            project_id=testProject.id,
            module="模块E",
            title="过期用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="旧摘�?,
            summary_model_version="old-model",
        )
        fresh_case = TestCase(
            case_no="FP-FRESH-DET",
            project_id=testProject.id,
            module="模块E",
            title="新鲜用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="新摘�?,
            summary_model_version="mock-model",
        )
        db.add_all([stale_case, fresh_case])
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="fingerprint_stale_det_hash",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=mock_ai,
            run=run,
            iteration_id=iteration.id,
            user_id=1,
        )

        raw_signals = _make_raw_signals(testProject.id)
        artifact = Artifact(
            run_id=run.id,
            kind="raw_signals",
            schema_version="1.0",
            payload=raw_signals,
            content_hash="test_raw_signals_stale_det",
        )
        db.add(artifact)
        db.flush()
        ctx.set_artifact("raw_signals", artifact)

        count = _detect_stale_summaries(ctx, testProject.id)

        assert count >= 1

    def test_no_stale_returns_zero(self, db, make_ctx, test_iteration):
        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        count = _detect_stale_summaries(ctx, test_iteration.project_id)
        assert count == 0


class TestIncrementalBackfillReturnValue:
    def test_backfill_returns_count(self, db, make_ctx, mock_ai, test_iteration):
        case = TestCase(
            case_no="FP-BACKFILL-RET",
            project_id=test_iteration.project_id,
            module="模块F",
            title="回填返回值用�?,
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="旧摘�?,
            summary_version=1,
            summary_model_version="old-model-v2",
        )
        db.add(case)
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        backfilled = _incremental_backfill(ctx, test_iteration.project_id)

        assert backfilled >= 1


class TestLoadFingerprintsPagination:
    def test_module_filter(self, db, make_ctx, test_iteration):
        case_a = TestCase(
            case_no="FP-MOD-A",
            project_id=test_iteration.project_id,
            module="模块A",
            title="模块A用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
        )
        case_b = TestCase(
            case_no="FP-MOD-B",
            project_id=test_iteration.project_id,
            module="模块B",
            title="模块B用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
        )
        db.add_all([case_a, case_b])
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        fps = _load_fingerprints(ctx, test_iteration.project_id, module="模块A")

        assert all(fp["module"] == "模块A" for fp in fps)
        assert any(fp["case_id"] == case_a.id for fp in fps)

    def test_limit_and_offset(self, db, make_ctx, test_iteration):
        for i in range(5):
            case = TestCase(
                case_no=f"FP-PAGE-{i}",
                project_id=test_iteration.project_id,
                module="模块P",
                title=f"分页用例{i}",
                precondition="�?,
                steps_json=[],
                expected_result="预期",
                priority=2,
                case_type="functional",
                lifecycle_status="active",
            )
            db.add(case)
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        fps = _load_fingerprints(ctx, test_iteration.project_id, module="模块P", limit=2, offset=0)

        assert len(fps) <= 2


class TestFallbackNoRawSignals:
    def test_fallback_without_raw_signals_in_ctx(self, make_ctx):
        ctx = make_ctx()
        step = HistoryFingerprint()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result is not None
        assert result.artifact_payload["project_id"] == 0


class TestBudgetCheckInBackfill:
    def test_backfill_stops_on_budget_exhaustion(self, db, make_ctx, mock_ai, test_iteration):
        case = TestCase(
            case_no="FP-BUDGET",
            project_id=test_iteration.project_id,
            module="模块G",
            title="预算测试用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="旧摘�?,
            summary_version=1,
            summary_model_version="old-budget-model",
        )
        db.add(case)
        db.flush()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))

        original_check = ctx.check_budget
        call_count = 0

        def fake_check():
            nonlocal call_count
            call_count += 1
            return call_count <= 0

        ctx.check_budget = fake_check

        backfilled = _incremental_backfill(ctx, test_iteration.project_id)
        assert backfilled == 0


class TestBackfillEmptyAiResponse:
    def test_backfill_skips_empty_summary(self, db, make_ctx, test_iteration):
        case = TestCase(
            case_no="FP-EMPTY-AI",
            project_id=test_iteration.project_id,
            module="模块H",
            title="空AI响应用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="旧摘�?,
            summary_version=1,
            summary_model_version="old-empty-model",
        )
        db.add(case)
        db.flush()

        empty_ai = MockAIClient()
        empty_ai.set_response("history_fingerprint_backfill", "")

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        ctx.ai_client = empty_ai

        backfilled = _incremental_backfill(ctx, test_iteration.project_id)
        assert backfilled == 0


class TestBackfillAiException:
    def test_backfill_handles_ai_exception(self, db, make_ctx, test_iteration):
        case = TestCase(
            case_no="FP-AI-ERR",
            project_id=test_iteration.project_id,
            module="模块I",
            title="AI异常用例",
            precondition="�?,
            steps_json=[],
            expected_result="预期",
            priority=2,
            case_type="functional",
            lifecycle_status="active",
            summary="旧摘�?,
            summary_version=1,
            summary_model_version="old-err-model",
        )
        db.add(case)
        db.flush()

        class FailingAIClient(MockAIClient):
            def complete(self, *args, **kwargs):
                raise ConnectionError("AI service unavailable")

        failing_ai = FailingAIClient()

        ctx = make_ctx(raw_signals_payload=_make_raw_signals(test_iteration.project_id))
        ctx.ai_client = failing_ai

        backfilled = _incremental_backfill(ctx, test_iteration.project_id)
        assert backfilled == 0


class TestBuildSummaryPromptStepsJsonError:
    def test_steps_json_serialization_error_fallback(self):
        class BadSteps:
            def __str__(self):
                return "bad-steps-repr"

        class FakeCase:
            title = "测试用例"
            precondition = "�?
            steps_json = BadSteps()
            expected_result = "预期"

        from app.pipelines.steps.history_fingerprint import _build_summary_prompt

        prompt = _build_summary_prompt(FakeCase())
        assert "bad-steps-repr" in prompt


class TestGetCurrentModelVersionFallback:
    def test_fallback_to_unknown_when_no_model_attr(self):
        class NoModelClient:
            pass

        from app.pipelines.steps.history_fingerprint import _get_current_model_version

        ctx = PipelineContext(
            db=None,
            ai_client=NoModelClient(),
            run=None,
            iteration_id=1,
        )

        version = _get_current_model_version(ctx)
        assert version == "unknown"

    def test_uses_model_name_attr(self):
        from app.pipelines.steps.history_fingerprint import _get_current_model_version

        client = MockAIClient()
        ctx = PipelineContext(
            db=None,
            ai_client=client,
            run=None,
            iteration_id=1,
        )

        version = _get_current_model_version(ctx)
        assert version == "mock-model"
