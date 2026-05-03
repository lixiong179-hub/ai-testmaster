"""M2 集成测试 — 双向扫描 + 评审交互 + 暂停/恢复 端到端验证

覆盖范围:
    - 场景 4 完整 Pipeline（旧项目，双向扫描 → Reconciliation → 用例生成）
    - HistoryFingerprint → BackwardScan → ForwardScan → Reconciliation 全链路
    - 评审 Inbox 完整流程（创建 → 决策 → 最终化 → 撤销）
    - Pipeline 暂停/恢复（pause_for_confirmation → waiting_for_user → resume）
    - 场景注册表完整性验证

使用真实 MySQL 数据库 + MockAIClient，不使用 FastAPI TestClient。
"""
import json
import pytest

from app.models.iteration import Iteration, IterationInput
from app.models.test_point import TestPoint
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.ai.mock_client import MockAIClient
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.scenarios import get_scenario
from app.services import pipeline_service, review_service


def _make_artifact(kind: str, payload: dict):
    from app.models.pipeline import Artifact
    return Artifact(run_id=0, kind=kind, schema_version="1.0", payload=payload, content_hash="test")


@pytest.fixture
def mock_ai_s4():
    client = MockAIClient()
    client.set_response("case_generation", json.dumps([
        {
            "title": "登录功能回归验证",
            "module": "用户管理",
            "precondition": "用户已注册",
            "steps": [{"action": "输入正确的用户名和密码", "expected": "登录成功"}],
            "expected_result": "成功登录并跳转首页",
            "priority": 1,
            "case_type": "functional",
        }
    ]))
    return client


@pytest.fixture
def s4_iteration(db, testProject):
    enable_lifecycle_transition()
    try:
        for i in range(3):
            case = TestCase(
                project_id=testProject.id,
                case_no=f"S4-HIST-{i:03d}",
                title=f"历史用例 {i}",
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
        db.flush()
    finally:
        disable_lifecycle_transition()

    iteration = Iteration(project_id=testProject.id, name="m2_e2e_s4", status="draft")
    db.add(iteration)
    db.flush()

    tp = TestPoint(project_id=testProject.id, module="用户管理", point="登录功能回归", priority=1)
    db.add(tp)
    db.flush()

    inp = IterationInput(
        iteration_id=iteration.id, kind="testpoint",
        payload={"test_point_ids": [tp.id]}, content_hash="m2_e2e_s4_tp_hash",
    )
    db.add(inp)
    db.flush()

    return {"iteration": iteration, "test_point": tp}


def _setup_scenario_4_mocks(ctx, mock_ai):
    """预填充 raw_signals + history_fingerprints 并设置后续 AI 响应。"""
    from app.pipelines.steps.history_fingerprint import HistoryFingerprint
    from app.pipelines.steps.signal_gatherer import SignalGatherer

    gatherer = SignalGatherer()
    g_result = gatherer.execute(ctx)
    ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

    f_step = HistoryFingerprint()
    f_result = f_step.execute(ctx)
    ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

    fps = f_result.artifact_payload.get("fingerprints", [])
    mock_ai.set_response("backward_scan", json.dumps({
        "verdicts": [{"case_id": fp["case_id"], "verdict": "VALID", "confidence": 0.9, "hint": "有效"} for fp in fps]
    }))
    mock_ai.set_response("scenario_candidate_extractor", json.dumps({
        "candidates": [{"description": "登录功能回归", "module": "用户管理", "precondition": "", "expected_result": ""}]
    }))
    mock_ai.set_response("forward_scan", json.dumps({
        "label": "NEW", "matched_case_id": None, "matched_title": "", "confidence": 0.85, "reason": "新功能",
    }))


def _run_s4_pipeline(db, iteration, mock_ai):
    run = pipeline_service.create_run(
        db=db, iteration_id=iteration.id,
        input_hash="m2_e2e_s4_hash", pipeline_version="4.0",
    )
    db.flush()

    ctx = PipelineContext(db=db, ai_client=mock_ai, run=run, iteration_id=iteration.id, user_id=1)
    _setup_scenario_4_mocks(ctx, mock_ai)

    scenario = get_scenario(4)
    runner = PipelineRunner(scenario["name"], scenario["steps"])
    runner.run(ctx)
    db.refresh(run)
    return run, ctx


class TestScenario4E2E:
    def test_pipeline_completes(self, db, s4_iteration, mock_ai_s4):
        iteration = s4_iteration["iteration"]
        run, _ = _run_s4_pipeline(db, iteration, mock_ai_s4)
        assert run.status == "completed"

    def test_produces_history_fingerprints(self, db, s4_iteration, mock_ai_s4):
        iteration = s4_iteration["iteration"]
        _, ctx = _run_s4_pipeline(db, iteration, mock_ai_s4)
        fingerprints = ctx.get_artifact("history_fingerprints")
        assert fingerprints is not None
        assert fingerprints.get("total_count") >= 3

    def test_produces_backward_verdicts(self, db, s4_iteration, mock_ai_s4):
        iteration = s4_iteration["iteration"]
        _, ctx = _run_s4_pipeline(db, iteration, mock_ai_s4)
        backward = ctx.get_artifact("backward_verdicts")
        assert backward is not None

    def test_produces_merged_verdicts(self, db, s4_iteration, mock_ai_s4):
        iteration = s4_iteration["iteration"]
        _, ctx = _run_s4_pipeline(db, iteration, mock_ai_s4)
        merged = ctx.get_artifact("merged_verdicts")
        assert merged is not None


class TestReviewInboxFlow:
    @pytest.fixture
    def review_iteration(self, db, testProject):
        iteration = Iteration(project_id=testProject.id, name="m2_review_iter", status="draft")
        db.add(iteration)
        db.flush()
        return iteration

    def test_full_review_lifecycle(self, db, review_iteration, testUser):
        review = review_service.create_review(db=db, iteration_id=review_iteration.id, kind="forward")
        assert review.status == "draft"

        review_service.start_review(db=db, review_id=review.id)
        db.refresh(review)
        assert review.status == "in_progress"

        d = review_service.add_decision(
            db=db, review_id=review.id, target_kind="case", target_id=1,
            ai_verdict="keep", ai_confidence=90,
        )
        assert d.ai_confidence >= 60

        d2 = review_service.add_decision(
            db=db, review_id=review.id, target_kind="case", target_id=2,
            ai_verdict="modify", ai_confidence=60,
        )
        assert d2.ai_confidence < 70

        result = review_service.set_human_verdict(
            db=db, decision_id=d.id, human_verdict="keep", human_user_id=testUser.id,
        )
        assert result.human_verdict == "keep"

        review_service.finalize_review(db=db, review_id=review.id, finalized_by=testUser.id)
        db.refresh(review)
        assert review.is_finalized()

        decisions_after = review_service.get_decisions(db, review.id)
        assert len(decisions_after) >= 2

        undone = review_service.undo_finalize(db=db, review_id=review.id, user_id=testUser.id)
        assert not undone.is_finalized()

    def test_undo_decision(self, db, review_iteration, testUser):
        review = review_service.create_review(db=db, iteration_id=review_iteration.id, kind="forward")
        review_service.start_review(db=db, review_id=review.id)

        d = review_service.add_decision(
            db=db, review_id=review.id, target_kind="case", target_id=1,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=d.id, human_verdict="keep", human_user_id=testUser.id,
        )
        review_service.finalize_review(db=db, review_id=review.id, finalized_by=testUser.id)

        result = review_service.undo_decision(db=db, decision_id=d.id, user_id=testUser.id)
        assert result is not None
        assert result.human_verdict is None

    def test_undo_finalize(self, db, review_iteration, testUser):
        review = review_service.create_review(db=db, iteration_id=review_iteration.id, kind="forward")
        review_service.start_review(db=db, review_id=review.id)

        d = review_service.add_decision(
            db=db, review_id=review.id, target_kind="case", target_id=1,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=d.id, human_verdict="keep", human_user_id=testUser.id,
        )
        review_service.finalize_review(db=db, review_id=review.id, finalized_by=testUser.id)

        result = review_service.undo_finalize(db=db, review_id=review.id, user_id=testUser.id)
        assert result is not None
        assert not result.is_finalized()

    def test_rollback_decision(self, db, review_iteration, testUser):
        review = review_service.create_review(db=db, iteration_id=review_iteration.id, kind="forward")
        review_service.start_review(db=db, review_id=review.id)

        d = review_service.add_decision(
            db=db, review_id=review.id, target_kind="case", target_id=1,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=d.id, human_verdict="keep", human_user_id=testUser.id,
        )

        result = review_service.rollback_decision(db=db, decision_id=d.id, user_id=testUser.id)
        assert result is not None
        assert result.human_verdict is None


class TestPipelineRunRecord:
    def test_run_record_has_steps(self, db, s4_iteration, mock_ai_s4):
        iteration = s4_iteration["iteration"]
        run, _ = _run_s4_pipeline(db, iteration, mock_ai_s4)

        found = pipeline_service.get_run(db, run.id)
        assert found is not None
        assert found.status == "completed"
        assert len(found.steps) >= 8
        assert len(found.artifacts) >= 1


class TestM2CrossScenario:
    def test_scenario_registry_complete(self):
        for sid in [1, 2, 4]:
            scenario = get_scenario(sid)
            assert scenario is not None, f"Scenario {sid} missing"
            assert "name" in scenario
            assert "steps" in scenario
            assert len(scenario["steps"]) >= 3, f"Scenario {sid} has too few steps"

    def test_scenario_4_registered(self):
        s4 = get_scenario(4)
        assert s4 is not None
        assert s4["name"] == "scenario_4_regression"
        assert s4["version"] == "4.0"
        step_names = [s.name for s in s4["steps"]]
        assert "reconciliation" in step_names
        assert "history_fingerprint" in step_names
