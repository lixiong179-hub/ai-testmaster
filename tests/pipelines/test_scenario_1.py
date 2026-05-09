"""
M1-T11 场景 1 流水线端到端测试

覆盖�?
    - SignalGatherer 信号采集
    - TestPointAlignment 测试点对�?
    - CaseGeneration 用例生成
    - QualityGate 先验质量�?
    - Persist 用例持久�?
    - 场景 1 完整 Pipeline 端到�?
    - �?Step �?should_run / cache_key / validate_output / fallback
"""
import json
import pytest
from typing import ClassVar, List

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist
from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration, IterationInput
from app.models.test_point import TestPoint
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.models.pipeline import PipelineRun
from app.services import pipeline_service


def _make_artifact(kind: str, payload: dict):
    """创建轻量�?Artifact 替身对象，兼�?PipelineContext.get_artifact 返回 payload 的约定�?""
    from app.models.pipeline import Artifact
    return Artifact(
        run_id=0,
        kind=kind,
        schema_version="1.0",
        payload=payload,
        content_hash="test",
    )


@pytest.fixture
def mock_ai():
    client = MockAIClient()
    client.set_response("case_generation", json.dumps([
        {
            "title": "登录功能验证",
            "module": "用户管理",
            "precondition": "用户已注�?,
            "steps": [
                {"action": "输入正确的用户名和密�?, "expected": "登录成功"},
                {"action": "点击登录按钮", "expected": "跳转到首�?},
            ],
            "expected_result": "成功登录并跳转首�?,
            "priority": 1,
            "case_type": "functional",
        }
    ]))
    return client


@pytest.fixture
def setup_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="scenario1_test",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    tp = TestPoint(
        project_id=testProject.id,
        module="用户管理",
        point="登录功能",
        priority=1,
    )
    db.add(tp)
    db.flush()

    inp = IterationInput(
        iteration_id=iteration.id,
        kind="testpoint",
        payload={"test_point_ids": [tp.id]},
        content_hash="test_hash_tp_001",
    )
    db.add(inp)
    db.flush()

    return {
        "iteration": iteration,
        "test_point": tp,
        "input": inp,
    }


@pytest.fixture
def make_ctx(db, mock_ai, setup_iteration):
    iteration = setup_iteration["iteration"]

    def _make_ctx():
        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="e2e_test_hash",
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

    return _make_ctx


class TestSignalGatherer:
    def test_execute_with_testpoint_input(self, db, make_ctx, setup_iteration):
        ctx = make_ctx()
        step = SignalGatherer()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "raw_signals"
        assert result.artifact_payload is not None
        assert result.artifact_payload["has_testpoints"] is True
        assert len(result.artifact_payload["test_points"]) >= 1
        assert result.artifact_confidence >= 0.3

    def test_should_run_always_true(self, make_ctx):
        ctx = make_ctx()
        step = SignalGatherer()
        assert step.should_run(ctx) is True

    def test_cache_key_deterministic(self, make_ctx):
        ctx = make_ctx()
        step = SignalGatherer()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64

    def test_validate_output_valid(self):
        step = SignalGatherer()
        payload = {
            "iteration_id": 1,
            "project_id": 1,
            "prd_content": "test",
            "test_points": [],
        }
        assert step.validate_output(payload) is True

    def test_validate_output_missing_field(self):
        step = SignalGatherer()
        assert step.validate_output({}) is False

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        step = SignalGatherer()
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.degraded is True
        assert result.success is False

    def test_execute_nonexistent_iteration(self, db, testProject, mock_ai):
        from app.services import pipeline_service
        from app.models.iteration import Iteration

        iteration = Iteration(project_id=testProject.id, name="orphan_iter", status="draft")
        db.add(iteration)
        db.flush()
        run = pipeline_service.create_run(db=db, iteration_id=iteration.id, input_hash="x", pipeline_version="1.0")
        db.flush()
        db.delete(iteration)
        db.flush()

        ctx = PipelineContext(db=db, ai_client=mock_ai, run=run, iteration_id=99999, user_id=1)
        step = SignalGatherer()
        result = step.execute(ctx)
        assert result.success is False
        assert "不存�? in result.error


class TestTestPointAlignment:
    def test_execute_with_signals(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        gather_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", gather_result.artifact_payload))

        step = TestPointAlignment()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "aligned_testpoints"
        assert result.artifact_payload["total_testpoints"] >= 1

    def test_should_run_false_without_signals(self, make_ctx):
        ctx = make_ctx()
        step = TestPointAlignment()
        assert step.should_run(ctx) is False

    def test_should_run_true_with_signals(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        gather_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", gather_result.artifact_payload))

        step = TestPointAlignment()
        assert step.should_run(ctx) is True

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        step = TestPointAlignment()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True
        assert result.success is True


class TestCaseGeneration:
    def test_execute_with_aligned_testpoints(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        aligner = TestPointAlignment()
        a_result = aligner.execute(ctx)
        ctx.set_artifact("aligned_testpoints", _make_artifact("aligned_testpoints", a_result.artifact_payload))

        step = CaseGeneration()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "generated_cases"
        assert result.artifact_payload["success_count"] >= 1

    def test_should_run_false_without_aligned(self, make_ctx):
        ctx = make_ctx()
        step = CaseGeneration()
        assert step.should_run(ctx) is False

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        step = CaseGeneration()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True

    def test_execute_ai_returns_empty(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        aligner = TestPointAlignment()
        a_result = aligner.execute(ctx)
        ctx.set_artifact("aligned_testpoints", _make_artifact("aligned_testpoints", a_result.artifact_payload))

        empty_ai = MockAIClient()
        empty_ai.set_response("case_generation", "")
        ctx.ai_client = empty_ai

        step = CaseGeneration()
        result = step.execute(ctx)
        assert result.artifact_payload["failed_count"] >= 1

    def test_execute_ai_returns_invalid_json(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        aligner = TestPointAlignment()
        a_result = aligner.execute(ctx)
        ctx.set_artifact("aligned_testpoints", _make_artifact("aligned_testpoints", a_result.artifact_payload))

        bad_ai = MockAIClient()
        bad_ai.set_response("case_generation", "this is not json at all")
        ctx.ai_client = bad_ai

        step = CaseGeneration()
        result = step.execute(ctx)
        assert result.artifact_payload["failed_count"] >= 1

    def test_execute_ai_raises_exception(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        aligner = TestPointAlignment()
        a_result = aligner.execute(ctx)
        ctx.set_artifact("aligned_testpoints", _make_artifact("aligned_testpoints", a_result.artifact_payload))

        class BrokenAIClient:
            def complete(self, *args, **kwargs):
                raise ConnectionError("AI service unavailable")

        ctx.ai_client = BrokenAIClient()

        step = CaseGeneration()
        result = step.execute(ctx)
        assert result.artifact_payload["failed_count"] >= 1


class TestQualityGate:
    def test_execute_with_generated_cases(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        aligner = TestPointAlignment()
        a_result = aligner.execute(ctx)
        ctx.set_artifact("aligned_testpoints", _make_artifact("aligned_testpoints", a_result.artifact_payload))

        gen = CaseGeneration()
        c_result = gen.execute(ctx)
        ctx.set_artifact("generated_cases", _make_artifact("generated_cases", c_result.artifact_payload))

        step = QualityGate()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "quality_scores"
        assert result.artifact_payload["average_score"] >= 0
        assert result.artifact_payload["average_grade"] in ("A", "B", "C", "D", "F")

    def test_should_run_false_without_cases(self, make_ctx):
        ctx = make_ctx()
        step = QualityGate()
        assert step.should_run(ctx) is False

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        step = QualityGate()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestPersist:
    def test_execute_persists_cases(self, db, make_ctx, mock_ai, testProject):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        aligner = TestPointAlignment()
        a_result = aligner.execute(ctx)
        ctx.set_artifact("aligned_testpoints", _make_artifact("aligned_testpoints", a_result.artifact_payload))

        gen = CaseGeneration()
        c_result = gen.execute(ctx)
        ctx.set_artifact("generated_cases", _make_artifact("generated_cases", c_result.artifact_payload))

        qg = QualityGate()
        q_result = qg.execute(ctx)
        ctx.set_artifact("quality_scores", _make_artifact("quality_scores", q_result.artifact_payload))

        step = Persist()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "persisted_case_ids"
        assert result.artifact_payload["total_persisted"] >= 1

        persisted_ids = result.artifact_payload["persisted_case_ids"]
        for cid in persisted_ids:
            case = db.query(TestCase).filter(TestCase.id == cid).first()
            assert case is not None
            assert case.lifecycle_status in ("draft", "pending_review")

    def test_should_run_false_without_cases(self, make_ctx):
        ctx = make_ctx()
        step = Persist()
        assert step.should_run(ctx) is False

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        step = Persist()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestScenario1E2E:
    def test_full_pipeline_run(self, db, make_ctx, mock_ai, testProject):
        ctx = make_ctx()

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(1)
        assert scenario is not None

        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

        persisted_artifact = ctx.get_artifact("persisted_case_ids")
        assert persisted_artifact is not None

    def test_pipeline_creates_test_cases(self, db, make_ctx, mock_ai, testProject):
        ctx = make_ctx()

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(1)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        cases = db.query(TestCase).filter(
            TestCase.project_id == testProject.id,
        ).all()
        assert len(cases) >= 1

    def test_pipeline_with_empty_iteration(self, db, testProject, mock_ai):
        iteration = Iteration(
            project_id=testProject.id,
            name="empty_iteration",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="empty_hash",
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

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(1)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status == "failed"

    def test_pipeline_with_prd_and_prototype_input(self, db, testProject, mock_ai):
        from app.models.project import ProjectFile
        from app.models.ui_prototype import UIPrototypeScreen

        iteration = Iteration(
            project_id=testProject.id,
            name="full_input_iteration",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        prd_file = ProjectFile(
            project_id=testProject.id,
            file_name="需求文�?docx",
            file_url="/tmp/prd.docx",
            file_type="docx",
            size=2048,
            resource_type="requirement",
            extract_status="completed",
            content="用户登录功能需求：支持账号密码登录和手机验证码登录",
        )
        db.add(prd_file)
        db.flush()

        prd_inp = IterationInput(
            iteration_id=iteration.id,
            kind="prd",
            file_id=prd_file.id,
            content_hash="prd_hash_001",
        )
        db.add(prd_inp)

        screen = UIPrototypeScreen(
            project_id=testProject.id,
            prototype_name="login_proto",
            screen_name="登录页面",
            screen_order=0,
            parse_status="completed",
            summary="登录界面",
            ui_spec={"elements": [{"type": "button", "text": "登录"}]},
        )
        db.add(screen)
        db.flush()

        proto_inp = IterationInput(
            iteration_id=iteration.id,
            kind="prototype",
            payload={"screen_ids": [screen.id]},
            content_hash="proto_hash_001",
        )
        db.add(proto_inp)

        tp = TestPoint(
            project_id=testProject.id,
            module="登录",
            point="账号密码登录",
            priority=1,
        )
        db.add(tp)
        db.flush()

        tp_inp = IterationInput(
            iteration_id=iteration.id,
            kind="testpoint",
            payload={"test_point_ids": [tp.id]},
            content_hash="tp_hash_001",
        )
        db.add(tp_inp)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="full_input_hash",
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

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(1)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status == "completed"

        signals = ctx.get_artifact("raw_signals")
        assert signals is not None
        assert signals.get("has_prd") is True
        assert signals.get("has_ui") is True
        assert signals.get("has_testpoints") is True

    def test_pipeline_with_xmind_input(self, db, testProject, mock_ai):
        iteration = Iteration(
            project_id=testProject.id,
            name="xmind_iteration",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        xmind_inp = IterationInput(
            iteration_id=iteration.id,
            kind="xmind",
            payload=None,
            content_hash="xmind_hash_001",
        )
        db.add(xmind_inp)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="xmind_input_hash",
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

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(1)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status in ("completed", "failed")
