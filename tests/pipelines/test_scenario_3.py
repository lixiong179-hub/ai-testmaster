"""
M3-T05 场景 3 流水线端到端测试（仅 UI 输入的新项目）

覆盖：
    - 场景注册表查询（get_scenario(3) 返回正确配置）
    - 依赖链验证（ReverseInfer → ScenarioCandidateExtractor → TestPointAlignment）
    - ReverseInfer 新项目模式（UI → inferred_capabilities + uncertain_questions）
    - 置信度 < 0.7 触发暂停
    - ScenarioCandidateExtractor 无历史指纹模式
    - TestPointAlignment 四源对齐（含反推能力）
    - 场景 3 完整 Pipeline 端到端
    - should_run / cache_key / validate_output / fallback
"""
import json
import pytest

from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.reverse_infer import ReverseInfer
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist
from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration, IterationInput
from app.models.test_case import TestCase
from app.models.ui_prototype import UIPrototypeScreen
from app.services import pipeline_service


def _make_artifact(kind: str, payload: dict):
    from app.models.pipeline import Artifact
    return Artifact(
        run_id=0,
        kind=kind,
        schema_version="1.0",
        payload=payload,
        content_hash="test",
    )


def _make_default_infer_response() -> str:
    return json.dumps({
        "inferred_capabilities": [
            {
                "name": "用户注册",
                "key": "user_registration",
                "description": "用户通过填写表单完成账号注册",
                "confidence": 0.85,
                "supporting_evidence": "注册页面包含用户名、密码、邮箱输入框和注册按钮",
            },
            {
                "name": "用户登录",
                "key": "user_login",
                "description": "已注册用户通过凭证登录系统",
                "confidence": 0.9,
                "supporting_evidence": "登录页面包含用户名、密码输入框和登录按钮",
            },
        ],
        "uncertain_questions": [
            {
                "question": "是否需要邮箱验证？",
                "context": "注册页面有邮箱输入框但未见验证码控件",
                "suggested_answer": "可能使用邮箱链接验证",
            },
        ],
        "overall_confidence": 0.85,
        "analysis_summary": "UI 显示注册和登录两个核心业务流程，共 2 个业务能力",
    })


def _make_low_confidence_infer_response() -> str:
    return json.dumps({
        "inferred_capabilities": [
            {
                "name": "不确定功能",
                "key": "uncertain_feature",
                "description": "不确定",
                "confidence": 0.3,
                "supporting_evidence": "信息不足",
            },
        ],
        "uncertain_questions": [
            {"question": "这是什么功能？", "context": "页面1", "suggested_answer": ""},
        ],
        "overall_confidence": 0.3,
        "analysis_summary": "不确定",
    })


def _make_default_candidates_response() -> str:
    return json.dumps({
        "candidates": [
            {
                "description": "用户注册流程验证",
                "module": "用户管理",
                "priority": 1,
                "reason": "核心注册流程需完整覆盖",
            },
            {
                "description": "用户登录流程验证",
                "module": "用户管理",
                "priority": 1,
                "reason": "核心登录流程需完整覆盖",
            },
            {
                "description": "密码找回流程验证",
                "module": "用户管理",
                "priority": 2,
                "reason": "忘记密码是常见场景",
            },
        ]
    })


def _make_default_cases_response() -> str:
    return json.dumps([
        {
            "title": "用户注册流程验证",
            "module": "用户管理",
            "precondition": "用户未注册",
            "steps": [
                {"action": "打开注册页面", "expected": "显示注册表单"},
                {"action": "填写用户名、密码、邮箱", "expected": "表单验证通过"},
                {"action": "点击注册按钮", "expected": "注册成功并跳转登录页"},
            ],
            "expected_result": "用户成功注册账号",
            "priority": 1,
            "case_type": "functional",
        },
    ])


@pytest.fixture
def mock_ai():
    client = MockAIClient()
    client.set_response("reverse_infer", _make_default_infer_response())
    client.set_response("scenario_candidate_extractor", _make_default_candidates_response())
    client.set_response("case_generation", _make_default_cases_response())
    client.set_response("case_generation_create", _make_default_cases_response())
    client.set_response("case_generation_modify", _make_default_cases_response())
    client.set_response("case_generation_locator", _make_default_cases_response())
    client.set_response("case_generation_supplement", _make_default_cases_response())
    return client


@pytest.fixture
def _setup_ui_screens(db, testProject):
    screen1 = UIPrototypeScreen(
        project_id=testProject.id,
        prototype_name="scenario3_proto",
        screen_name="登录页",
        source="manual",
        screen_order=0,
        parse_status="completed",
        summary="包含用户名输入框、密码输入框、登录按钮、忘记密码链接",
        ui_spec={
            "components": [
                {"type": "input", "name": "用户名"},
                {"type": "input", "name": "密码"},
                {"type": "button", "name": "登录"},
                {"type": "link", "name": "忘记密码"},
            ],
        },
    )
    screen2 = UIPrototypeScreen(
        project_id=testProject.id,
        prototype_name="scenario3_proto",
        screen_name="注册页",
        source="manual",
        screen_order=1,
        parse_status="completed",
        summary="包含用户名输入框、密码输入框、邮箱输入框、注册按钮",
        ui_spec={
            "components": [
                {"type": "input", "name": "用户名"},
                {"type": "input", "name": "密码"},
                {"type": "input", "name": "邮箱"},
                {"type": "button", "name": "注册"},
            ],
        },
    )
    db.add(screen1)
    db.add(screen2)
    db.flush()
    return [screen1, screen2]


@pytest.fixture
def setup_iteration_ui_only(db, testProject, _setup_ui_screens):
    screens = _setup_ui_screens
    iteration = Iteration(
        project_id=testProject.id,
        name="scenario3_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    ui_input = IterationInput(
        iteration_id=iteration.id,
        kind="prototype",
        payload={"screen_ids": [s.id for s in screens]},
        content_hash="s3_ui_hash_001",
    )
    db.add(ui_input)
    db.flush()

    return {
        "iteration": iteration,
        "ui_input": ui_input,
        "screens": screens,
    }


@pytest.fixture
def make_ctx(db, mock_ai, setup_iteration_ui_only):
    iteration = setup_iteration_ui_only["iteration"]

    def _make_ctx():
        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s3_e2e_hash",
            pipeline_version="3.0",
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


class TestScenario3Registry:
    def test_get_scenario_3(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        assert scenario is not None
        assert scenario["name"] == "scenario_3_ui_only"
        assert scenario["version"] == "3.0"

    def test_scenario_3_has_7_steps(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        assert len(scenario["steps"]) == 7

    def test_scenario_3_step_order(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        step_names = [s.name for s in scenario["steps"]]
        expected = [
            "signal_gatherer",
            "reverse_infer",
            "scenario_candidate_extractor",
            "testpoint_alignment",
            "case_generation",
            "quality_gate",
            "persist",
        ]
        assert step_names == expected

    def test_scenario_3_includes_reverse_infer(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        step_names = [s.name for s in scenario["steps"]]
        assert "reverse_infer" in step_names

    def test_scenario_3_no_history_steps(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        step_names = [s.name for s in scenario["steps"]]
        assert "history_fingerprint" not in step_names
        assert "backward_scan" not in step_names
        assert "forward_scan" not in step_names
        assert "reconciliation" not in step_names

    def test_nonexistent_scenario(self):
        from app.pipelines.scenarios import get_scenario
        assert get_scenario(999) is None


class TestDependencyChain:
    def test_reverse_infer_requires_raw_signals(self):
        assert "raw_signals" in ReverseInfer.requires
        assert "inferred_business_summary" in ReverseInfer.produces

    def test_testpoint_alignment_requires_raw_signals(self):
        assert "raw_signals" in TestPointAlignment.requires
        assert "aligned_testpoints" in TestPointAlignment.produces

    def test_scenario_candidates_requires_signals(self):
        assert "raw_signals" in ScenarioCandidateExtractor.requires
        assert "scenario_candidates" in ScenarioCandidateExtractor.produces

    def test_chain_from_signal_to_persist(self):
        assert SignalGatherer.produces == ["raw_signals"]
        assert ReverseInfer.produces == ["inferred_business_summary"]
        assert ScenarioCandidateExtractor.produces == ["scenario_candidates"]
        assert TestPointAlignment.produces == ["aligned_testpoints"]
        assert CaseGeneration.produces == ["generated_cases"]
        assert QualityGate.produces == ["quality_scores"]
        assert Persist.produces == ["persisted_case_ids"]


class TestReverseInferNewProject:
    def test_execute_infers_capabilities(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "inferred_business_summary"
        assert result.artifact_payload["is_old_project"] is False
        assert result.artifact_payload["mode"] == "new_project"
        parsed = result.artifact_payload.get("parsed", {})
        assert len(parsed.get("inferred_capabilities", [])) >= 2

    def test_confidence_high_no_pause(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        result = step.execute(ctx)

        assert result.success is True
        assert result.pause_for_confirmation is False

    def test_confidence_low_triggers_pause(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        mock_ai.set_response("reverse_infer", _make_low_confidence_infer_response())

        step = ReverseInfer()
        result = step.execute(ctx)

        assert result.success is True
        assert result.pause_for_confirmation is True
        assert result.confirmation_payload is not None
        assert len(result.confirmation_payload.get("questions", [])) >= 1

    def test_should_run_only_with_ui(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        assert step.should_run(ctx) is True

    def test_should_run_without_ui(self, make_ctx):
        ctx = make_ctx()
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", {
            "iteration_id": ctx.iteration_id,
            "project_id": 1,
            "has_ui": False,
            "prd_content": "",
            "ui_descriptions": [],
            "ui_specs": [],
            "test_points": [],
            "file_ids_used": [],
            "has_prd": False,
            "has_testpoints": False,
        }))

        step = ReverseInfer()
        assert step.should_run(ctx) is False

    def test_cache_key_deterministic(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64

    def test_validate_output_valid(self):
        step = ReverseInfer()
        assert step.validate_output({
            "iteration_id": 1,
            "project_id": 1,
            "parsed": {"overall_confidence": 0.85},
        }) is True

    def test_validate_output_missing(self):
        step = ReverseInfer()
        assert step.validate_output({"project_id": 1}) is False

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.degraded is True


class TestScenarioCandidateNoHistory:
    def test_execute_without_history(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ScenarioCandidateExtractor()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "scenario_candidates"
        assert "candidates" in result.artifact_payload
        assert result.artifact_payload["existing_modules"] == []

    def test_should_run_with_raw_signals(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ScenarioCandidateExtractor()
        assert step.should_run(ctx) is True

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ScenarioCandidateExtractor()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestTestPointAlignmentWithInferred:
    def test_execute_with_inferred_capabilities(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        reverse_infer = ReverseInfer()
        ri_result = reverse_infer.execute(ctx)
        ctx.set_artifact("inferred_business_summary",
                         _make_artifact("inferred_business_summary", ri_result.artifact_payload))

        step = TestPointAlignment()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "aligned_testpoints"

    def test_should_run_with_inferred_only(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        reverse_infer = ReverseInfer()
        ri_result = reverse_infer.execute(ctx)
        ctx.set_artifact("inferred_business_summary",
                         _make_artifact("inferred_business_summary", ri_result.artifact_payload))

        step = TestPointAlignment()
        assert step.should_run(ctx) is True


class TestScenario3E2E:
    def test_full_pipeline_run(self, db, make_ctx):
        ctx = make_ctx()

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "completed"

    def test_pipeline_generates_cases_from_ui_only(self, db, make_ctx, testProject):
        ctx = make_ctx()

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(ctx.run)
        cases = db.query(TestCase).filter(
            TestCase.project_id == testProject.id,
        ).all()
        assert len(cases) >= 1

    def test_pipeline_produces_artifacts(self, db, make_ctx):
        ctx = make_ctx()

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        inferred = ctx.get_artifact("inferred_business_summary")
        assert inferred is not None

        candidates = ctx.get_artifact("scenario_candidates")
        assert candidates is not None
        assert candidates.get("total_count") >= 2

        aligned = ctx.get_artifact("aligned_testpoints")
        assert aligned is not None

    def test_pipeline_pauses_on_low_confidence(self, db, make_ctx, mock_ai):
        ctx = make_ctx()

        mock_ai.set_response("reverse_infer", _make_low_confidence_infer_response())

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(3)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status == "waiting_for_user"
        assert ctx.run.pause_payload is not None
        assert ctx.run.pause_payload.get("step_name") == "reverse_infer"
