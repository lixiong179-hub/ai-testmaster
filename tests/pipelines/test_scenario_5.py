"""
M3-T06 场景 5 流水线端到端测试（旧项目无新 PRD�?

覆盖�?
    - 场景注册表查询（get_scenario(5) 返回正确配置�?
    - 依赖链验证（�?ReverseInfer �?TestPointAlignment 额外链）
    - ReverseInfer 旧项目无 UI 模式（历史指�?�?推断能力�?
    - 场景 5 完整 Pipeline 端到端（11 步）
    - 双向扫描 + Reconciliation 合并矩阵（与场景 4 共享�?
    - should_run / cache_key / validate_output / fallback
"""
import json
import pytest

from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.history_fingerprint import HistoryFingerprint
from app.pipelines.steps.reverse_infer import ReverseInfer
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.backward_scan import BackwardScan
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.forward_scan import ForwardScan
from app.pipelines.steps.reconciliation import Reconciliation
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist
from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration, IterationInput
from app.models.test_point import TestPoint
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
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


def _make_old_project_infer_response() -> str:
    return json.dumps({
        "inferred_capabilities": [
            {
                "name": "用户管理",
                "key": "user_management",
                "description": "用户登录、注册、信息管理的业务能力",
                "confidence": 0.88,
                "supporting_evidence": "历史用例涵盖登录和注册流�?,
            },
        ],
        "uncertain_questions": [],
        "overall_confidence": 0.88,
        "analysis_summary": "�?3 条历史用例推断出 1 个业务能力：用户管理",
    })


def _build_forward_mock(fingerprints: list) -> str:
    return json.dumps({
        "verdicts": [
            {
                "matched_case_id": fp["case_id"],
                "verdict": "NEEDS_MODIFY",
                "confidence": 0.8,
                "hint": "需微调",
                "locator_status": None,
            }
            for fp in fingerprints
        ] if fingerprints else []
    })


def _build_backward_mock(fingerprints: list) -> str:
    return json.dumps({
        "verdicts": [
            {
                "case_id": fp["case_id"],
                "verdict": "VALID",
                "confidence": 0.9,
                "hint": "仍然有效",
            }
            for fp in fingerprints
        ] if fingerprints else []
    })


def _build_candidate_mock() -> str:
    return json.dumps({
        "candidates": [
            {"description": "登录功能回归", "module": "用户管理",
             "precondition": "", "expected_result": ""},
        ]
    })


def _build_case_gen_mock() -> str:
    return json.dumps([
        {
            "title": "登录功能回归验证",
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
    ])


@pytest.fixture
def mock_ai():
    client = MockAIClient()
    client.set_response("reverse_infer", _make_old_project_infer_response())
    client.set_response("case_generation", _build_case_gen_mock())
    return client


@pytest.fixture
def setup_iteration_with_history(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="scenario5_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    tp = TestPoint(
        project_id=testProject.id,
        module="用户管理",
        point="登录功能回归",
        priority=1,
    )
    db.add(tp)
    db.flush()

    inp = IterationInput(
        iteration_id=iteration.id,
        kind="testpoint",
        payload={"test_point_ids": [tp.id]},
        content_hash="s5_tp_hash_001",
    )
    db.add(inp)
    db.flush()

    enable_lifecycle_transition()
    try:
        historical_cases = []
        for i in range(3):
            case = TestCase(
                project_id=testProject.id,
                case_no=f"S5-HIST-{i:03d}",
                title=f"历史用例 {i} - 登录功能",
                module="用户管理",
                precondition="",
                steps_json=[{"action": "操作", "expected": "预期"}],
                expected_result="通过",
                priority=1,
                case_type="functional",
                lifecycle_status="active",
                summary=f"历史用例 {i} 摘要",
            )
            db.add(case)
            historical_cases.append(case)
        db.flush()
    finally:
        disable_lifecycle_transition()

    return {
        "iteration": iteration,
        "test_point": tp,
        "input": inp,
        "historical_cases": historical_cases,
    }


@pytest.fixture
def make_ctx(db, mock_ai, setup_iteration_with_history):
    iteration = setup_iteration_with_history["iteration"]

    def _make_ctx():
        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s5_e2e_hash",
            pipeline_version="5.0",
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


def _setup_e2e_mocks(mock_ai, ctx):
    gatherer = SignalGatherer()
    g_result = gatherer.execute(ctx)
    ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

    fingerprinter = HistoryFingerprint()
    f_result = fingerprinter.execute(ctx)
    ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

    fps = f_result.artifact_payload.get("fingerprints", [])
    mock_ai.set_response("backward_scan", _build_backward_mock(fps))
    mock_ai.set_response("scenario_candidate_extractor", _build_candidate_mock())
    mock_ai.set_response("forward_scan", _build_forward_mock(fps))

    return ctx, fps


class TestScenario5Registry:
    def test_get_scenario_5(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        assert scenario is not None
        assert scenario["name"] == "scenario_5_old_project_no_prd"
        assert scenario["version"] == "5.0"

    def test_scenario_5_has_11_steps(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        assert len(scenario["steps"]) == 11

    def test_scenario_5_step_order(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        step_names = [s.name for s in scenario["steps"]]
        expected = [
            "signal_gatherer",
            "history_fingerprint",
            "reverse_infer",
            "testpoint_alignment",
            "backward_scan",
            "scenario_candidate_extractor",
            "forward_scan",
            "reconciliation",
            "case_generation",
            "quality_gate",
            "persist",
        ]
        assert step_names == expected

    def test_scenario_5_includes_reverse_infer(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        step_names = [s.name for s in scenario["steps"]]
        assert "reverse_infer" in step_names

    def test_scenario_5_includes_bidirectional_scan(self):
        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        step_names = [s.name for s in scenario["steps"]]
        assert "backward_scan" in step_names
        assert "forward_scan" in step_names
        assert "reconciliation" in step_names

    def test_scenario_5_differs_from_4(self):
        from app.pipelines.scenarios import get_scenario
        s5 = get_scenario(5)
        s4 = get_scenario(4)
        assert s5["name"] != s4["name"]
        assert s5["version"] != s4["version"]

    def test_nonexistent_scenario(self):
        from app.pipelines.scenarios import get_scenario
        assert get_scenario(999) is None


class TestDependencyChain:
    def test_signal_gatherer_produces_raw_signals(self):
        assert "raw_signals" in SignalGatherer.produces

    def test_reverse_infer_produces_business_summary(self):
        assert "inferred_business_summary" in ReverseInfer.produces

    def test_history_fingerprint_requires_raw_signals(self):
        assert "raw_signals" in HistoryFingerprint.requires
        assert "history_fingerprints" in HistoryFingerprint.produces

    def test_reverse_infer_requires_raw_signals(self):
        assert "raw_signals" in ReverseInfer.requires

    def test_backward_scan_requires_fingerprints_and_signals(self):
        assert "history_fingerprints" in BackwardScan.requires
        assert "raw_signals" in BackwardScan.requires
        assert "backward_verdicts" in BackwardScan.produces

    def test_forward_scan_requires_candidates_and_fingerprints(self):
        assert "scenario_candidates" in ForwardScan.requires
        assert "history_fingerprints" in ForwardScan.requires
        assert "forward_verdicts" in ForwardScan.produces

    def test_reconciliation_requires_both_verdicts(self):
        assert "backward_verdicts" in Reconciliation.requires
        assert "forward_verdicts" in Reconciliation.requires
        assert "merged_verdicts" in Reconciliation.produces

    def test_persist_requires_cases_and_scores(self):
        assert "generated_cases" in Persist.requires
        assert "quality_scores" in Persist.requires
        assert "persisted_case_ids" in Persist.produces

    def test_chain_from_signal_to_persist(self):
        assert SignalGatherer.produces == ["raw_signals"]
        assert HistoryFingerprint.produces == ["history_fingerprints"]
        assert ReverseInfer.produces == ["inferred_business_summary"]
        assert BackwardScan.produces[0] in Reconciliation.requires
        assert ForwardScan.produces[0] in Reconciliation.requires
        assert Reconciliation.produces == ["merged_verdicts"]
        assert CaseGeneration.produces == ["generated_cases"]
        assert QualityGate.produces == ["quality_scores"]
        assert Persist.produces == ["persisted_case_ids"]


class TestReverseInferOldProject:
    def test_execute_old_project_no_ui_mode(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        step = ReverseInfer()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "inferred_business_summary"
        assert result.artifact_payload["is_old_project"] is True
        assert result.artifact_payload["mode"] == "old_project"
        parsed = result.artifact_payload.get("parsed", {})
        assert len(parsed.get("inferred_capabilities", [])) >= 1

    def test_should_run_old_project_without_ui(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        assert step.should_run(ctx) is True

    def test_should_run_new_project_without_ui(self, make_ctx):
        ctx = make_ctx()
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", {
            "iteration_id": ctx.iteration_id,
            "project_id": 1,
            "has_ui": False,
            "is_old_project": False,
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

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        step = ReverseInfer()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ReverseInfer()
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.degraded is True


class TestHistoryFingerprint:
    def test_execute_with_history(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = HistoryFingerprint()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "history_fingerprints"
        assert result.artifact_payload["total_count"] >= 3

    def test_should_run_only_with_signals(self, make_ctx):
        ctx = make_ctx()
        step = HistoryFingerprint()
        assert step.should_run(ctx) is False

    def test_cache_key_deterministic(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = HistoryFingerprint()
        key1 = step.cache_key(ctx)
        key2 = step.cache_key(ctx)
        assert key1 == key2
        assert len(key1) == 64

    def test_fallback_returns_degraded(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = HistoryFingerprint()
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.degraded is True


class TestBackwardScan:
    def test_execute(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        fps = f_result.artifact_payload.get("fingerprints", [])
        mock_ai.set_response("backward_scan", _build_backward_mock(fps))

        step = BackwardScan()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "backward_verdicts"
        assert "verdicts" in result.artifact_payload

    def test_should_run_without_fingerprints(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = BackwardScan()
        assert step.should_run(ctx) is False

    def test_validate_output_valid(self):
        step = BackwardScan()
        assert step.validate_output({"project_id": 1, "verdicts": [], "total_count": 0, "stats": {}}) is True

    def test_validate_output_missing(self):
        step = BackwardScan()
        assert step.validate_output({"project_id": 1}) is False

    def test_fallback_returns_degraded(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        step = BackwardScan()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestScenarioCandidateExtractor:
    def test_execute(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        mock_ai.set_response("scenario_candidate_extractor", _build_candidate_mock())

        step = ScenarioCandidateExtractor()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "scenario_candidates"
        assert "candidates" in result.artifact_payload

    def test_should_run_with_raw_signals(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        step = ScenarioCandidateExtractor()
        assert step.should_run(ctx) is True

    def test_fallback_returns_degraded(self, db, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        step = ScenarioCandidateExtractor()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestForwardScan:
    def test_execute(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        mock_ai.set_response("scenario_candidate_extractor", _build_candidate_mock())
        candidate_step = ScenarioCandidateExtractor()
        c_result = candidate_step.execute(ctx)
        ctx.set_artifact("scenario_candidates", _make_artifact("scenario_candidates", c_result.artifact_payload))

        fps = f_result.artifact_payload.get("fingerprints", [])
        mock_ai.set_response("forward_scan", _build_forward_mock(fps))

        step = ForwardScan()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "forward_verdicts"
        assert "verdicts" in result.artifact_payload

    def test_should_run_without_candidates(self, make_ctx):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        step = ForwardScan()
        assert step.should_run(ctx) is False

    def test_fallback_returns_degraded(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        forward = ForwardScan()
        result = forward.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestReconciliation:
    def test_execute(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        fps = f_result.artifact_payload.get("fingerprints", [])

        mock_ai.set_response("backward_scan", _build_backward_mock(fps))
        mock_ai.set_response("scenario_candidate_extractor", _build_candidate_mock())
        mock_ai.set_response("forward_scan", _build_forward_mock(fps))

        candidate_step = ScenarioCandidateExtractor()
        c_result = candidate_step.execute(ctx)
        ctx.set_artifact("scenario_candidates", _make_artifact("scenario_candidates", c_result.artifact_payload))

        forward = ForwardScan()
        fw_result = forward.execute(ctx)
        ctx.set_artifact("forward_verdicts", _make_artifact("forward_verdicts", fw_result.artifact_payload))

        backward = BackwardScan()
        bw_result = backward.execute(ctx)
        ctx.set_artifact("backward_verdicts", _make_artifact("backward_verdicts", bw_result.artifact_payload))

        step = Reconciliation()
        result = step.execute(ctx)

        assert result.success is True
        assert result.artifact_kind == "merged_verdicts"
        payload = result.artifact_payload
        merged_data = payload.get("merged") or payload.get("verdicts")
        assert merged_data is not None
        assert len(merged_data) >= 1

    def test_should_run_missing_verdicts(self, make_ctx):
        ctx = make_ctx()
        step = Reconciliation()
        assert step.should_run(ctx) is False

    def test_fallback_returns_degraded(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        gatherer = SignalGatherer()
        g_result = gatherer.execute(ctx)
        ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

        fingerprinter = HistoryFingerprint()
        f_result = fingerprinter.execute(ctx)
        ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

        ctx.set_artifact("forward_verdicts", _make_artifact("forward_verdicts", {"verdicts": []}))
        ctx.set_artifact("backward_verdicts", _make_artifact("backward_verdicts", {"verdicts": []}))

        step = Reconciliation()
        result = step.fallback(ctx, RuntimeError("test"))
        assert result.degraded is True


class TestScenario5E2E:
    @pytest.fixture(autouse=True)
    def _setup_mocks(self, mock_ai):
        pass

    def test_full_pipeline_run(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        _setup_e2e_mocks(mock_ai, ctx)

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status in ("completed", "failed")

    def test_pipeline_generates_cases_from_history(self, db, make_ctx, mock_ai, testProject):
        ctx = make_ctx()
        _setup_e2e_mocks(mock_ai, ctx)

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(ctx.run)
        assert ctx.run.status in ("completed", "failed")

    def test_pipeline_produces_all_artifacts(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        _setup_e2e_mocks(mock_ai, ctx)

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        fingerprints = ctx.get_artifact("history_fingerprints")
        assert fingerprints is not None
        assert fingerprints.get("total_count") >= 3

        inferred = ctx.get_artifact("inferred_business_summary")
        assert inferred is not None
        assert inferred.get("is_old_project") is True

    def test_reverse_infer_runs_in_old_project_mode(self, db, make_ctx, mock_ai):
        ctx = make_ctx()
        _setup_e2e_mocks(mock_ai, ctx)

        from app.pipelines.scenarios import get_scenario
        scenario = get_scenario(5)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        inferred = ctx.get_artifact("inferred_business_summary")
        assert inferred is not None
        assert inferred["is_old_project"] is True
        assert inferred["mode"] == "old_project"
        parsed = inferred.get("parsed", {})
        caps = parsed.get("inferred_capabilities", [])
        assert len(caps) >= 1
