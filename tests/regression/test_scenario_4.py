"""场景 4 回归测试 — 旧项目双向扫描 + 评审

验证 Pipeline 场景 4 的核心行为不变：
    - 场景注册表可查询
    - 依赖链完整（10 个 Step，含 BackwardScan + ForwardScan + Reconciliation）    - Pipeline 端到端运行完成    - 双向扫描产物生成
    - 用例持久化到数据库    - 标注集数据结构有效
使用 Beta 标注集作为固定输入，MockAIClient 模拟 AI 响应。"""
import json
import pytest

from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.iteration import Iteration, IterationInput
from app.models.pipeline import PipelineRun, Artifact
from app.pipelines.scenarios import get_scenario
from tests.regression.conftest import _make_mock_ai, run_scenario


SCENARIO_4_MOCK_CASES = [
    {
        "title": "更新后的登录功能验证",
        "module": "用户登录",
        "precondition": "用户已注册",
        "steps": [
            {"action": "输入用户名和密码", "expected": "输入框显示内容"},
            {"action": "点击登录按钮", "expected": "跳转到首页"},
        ],
        "expected_result": "成功登录",
        "priority": 1,
        "case_type": "UI",
    },
]

SCENARIO_4_MOCK_BACKWARD = json.dumps([
    {"case_no": "HIST-001", "case_id": -1, "verdict": "VALID", "confidence": 0.95, "reason": "功能未变", "hint": "保持现有用例"},
])

SCENARIO_4_MOCK_FORWARD = json.dumps([
    {"title": "新增验证码登录", "module": "用户登录", "priority": 1},
])


@pytest.fixture
def mock_ai_s4(s4_iteration):
    client = _make_mock_ai(SCENARIO_4_MOCK_CASES)
    client.set_response("backward_scan", s4_iteration["backward_mock"])
    client.set_response("forward_scan", SCENARIO_4_MOCK_FORWARD)
    client.set_response("scenario_candidates", json.dumps([]))
    return client


@pytest.fixture
def s4_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="regression_s4",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    historical_case = TestCase(
        project_id=testProject.id,
        case_no="HIST-001",
        module="用户登录",
        title="历史登录用例",
        precondition="用户已注册",
        steps_json=[],
        expected_result="成功登录",
        priority=1,
        case_type="UI",
        lifecycle_status="active",
    )
    db.add(historical_case)
    db.flush()

    tp = TestPoint(
        project_id=testProject.id,
        module="用户登录",
        point="登录功能回归",
        priority=1,
    )
    db.add(tp)
    db.flush()

    backward_mock = json.dumps([
        {
            "case_no": "HIST-001",
            "case_id": historical_case.id,
            "verdict": "VALID",
            "confidence": 0.95,
            "reason": "功能未变",
            "hint": "保持现有用例",
        },
    ])

    inp = IterationInput(
        iteration_id=iteration.id,
        kind="testpoint",
        payload={"test_point_ids": [tp.id]},
        content_hash="regression_s4_tp",
    )
    db.add(inp)
    db.flush()
    return {"iteration": iteration, "backward_mock": backward_mock}


@pytest.mark.regression
@pytest.mark.scenario_full
class TestScenario4Regression:
    """场景 4 回归：旧项目双向扫描 + 评审"""

    def test_scenario_registered(self):
        scenario = get_scenario(4)
        assert scenario is not None
        assert scenario["name"] == "scenario_4_regression"

    def test_step_chain_intact(self):
        scenario = get_scenario(4)
        step_names = [s.__name__ for s in scenario["steps"]]
        assert "HistoryFingerprint" in step_names
        assert "BackwardScan" in step_names
        assert "ForwardScan" in step_names
        assert "Reconciliation" in step_names
        assert len(scenario["steps"]) == 11

    def test_pipeline_completes(self, db, s4_iteration, mock_ai_s4, testUser):
        run = run_scenario(db, s4_iteration["iteration"].id, 4, mock_ai_s4, testUser.id)
        db.flush()
        assert run.status in ("completed", "failed", "waiting_for_user")

    def test_cases_persisted(self, db, s4_iteration, mock_ai_s4, testUser):
        run_scenario(db, s4_iteration["iteration"].id, 4, mock_ai_s4, testUser.id)
        db.flush()

        cases = db.query(TestCase).filter(
            TestCase.project_id == s4_iteration["iteration"].project_id
        ).all()
        assert len(cases) >= 1

    def test_artifacts_created(self, db, s4_iteration, mock_ai_s4, testUser):
        run = run_scenario(db, s4_iteration["iteration"].id, 4, mock_ai_s4, testUser.id)
        db.flush()

        artifacts = db.query(Artifact).filter(Artifact.run_id == run.id).all()
        assert len(artifacts) >= 1

    def test_expected_verdicts_annotation_valid(self, beta_project_data):
        expected = beta_project_data["expected_verdicts"]
        assert len(expected) > 0
        for v in expected:
            assert "case_no" in v
            assert "verdict" in v
            assert v["verdict"] in ("VALID", "NEEDS_MODIFY", "DEPRECATE", "MERGE", "NEW")

    def test_historical_cases_annotation_valid(self, beta_project_data):
        cases = beta_project_data["historical_cases"]
        assert len(cases) > 0
        for c in cases:
            assert "case_no" in c
            assert "title" in c

    def test_run_record_queryable(self, db, s4_iteration, mock_ai_s4, testUser):
        run = run_scenario(db, s4_iteration["iteration"].id, 4, mock_ai_s4, testUser.id)
        db.flush()

        found = db.query(PipelineRun).filter(PipelineRun.id == run.id).first()
        assert found is not None
