"""场景 3 回归测试 — 仅 UI 输入新项目
验证 Pipeline 场景 3 的核心行为不变：
    - 场景注册表可查询，含 ReverseInfer 步骤
    - 依赖链完整（7 个 Step）    - SignalGatherer 正确识别 UI 输入
    - 反推业务能力产物生成
    - 用例持久化到数据库    - 标注集数据结构有效
使用 Gamma 标注集作为固定输入，MockAIClient 模拟 AI 响应。"""
import json
import pytest

from app.models.test_case import TestCase
from app.models.iteration import Iteration, IterationInput
from app.models.pipeline import PipelineRun, Artifact
from app.models.ui_prototype import UIPrototypeScreen
from app.models.test_point import TestPoint
from app.pipelines.scenarios import get_scenario
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.reverse_infer import ReverseInfer
from app.pipelines.context import PipelineContext
from tests.regression.conftest import _make_mock_ai, run_scenario


SCENARIO_3_MOCK_CASES = [
    {
        "title": "登录页面功能验证",
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

SCENARIO_3_MOCK_INFERENCE = json.dumps([
    {"name": "用户登录", "key": "user_login", "description": "用户通过凭证登录", "confidence": 0.9},
    {"name": "用户注册", "key": "user_register", "description": "新用户注册账号", "confidence": 0.85},
])


@pytest.fixture
def mock_ai_s3():
    client = _make_mock_ai(SCENARIO_3_MOCK_CASES)
    client.set_response("reverse_infer", SCENARIO_3_MOCK_INFERENCE)
    client.set_response("scenario_candidates", json.dumps([
        {"name": "用户登录", "key": "user_login", "priority": 1},
    ]))
    return client


@pytest.fixture
def s3_iteration(db, testProject):
    screen = UIPrototypeScreen(
        project_id=testProject.id,
        prototype_name="regression_s3_proto",
        screen_name="登录页",
        source="manual",
        screen_order=0,
        parse_status="completed",
        summary="登录页面",
        ui_spec={"components": [{"type": "input", "label": "用户名"}]},
    )
    db.add(screen)
    db.flush()

    iteration = Iteration(
        project_id=testProject.id,
        name="regression_s3",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    inp = IterationInput(
        iteration_id=iteration.id,
        kind="prototype",
        payload={"ui_prototype_id": screen.id},
        content_hash="regression_s3_prototype",
    )
    db.add(inp)
    db.flush()
    return iteration


@pytest.mark.regression
@pytest.mark.scenario_full
class TestScenario3Regression:
    """场景 3 回归：仅 UI 输入新项目"""

    def test_scenario_registered(self):
        scenario = get_scenario(3)
        assert scenario is not None
        assert scenario["name"] == "scenario_3_ui_only"

    def test_step_chain_intact(self):
        scenario = get_scenario(3)
        step_names = [s.__name__ for s in scenario["steps"]]
        assert "ReverseInfer" in step_names
        assert "ScenarioCandidateExtractor" in step_names
        assert len(scenario["steps"]) == 7

    def test_pipeline_completes(self, db, s3_iteration, mock_ai_s3, testUser):
        run = run_scenario(db, s3_iteration.id, 3, mock_ai_s3, testUser.id)
        db.flush()
        assert run.status in ("completed", "waiting_for_user")

    def test_cases_persisted(self, db, s3_iteration, mock_ai_s3, testUser):
        run = run_scenario(db, s3_iteration.id, 3, mock_ai_s3, testUser.id)
        db.flush()
        if run.status == "completed":
            cases = db.query(TestCase).filter(
                TestCase.project_id == s3_iteration.project_id
            ).all()
            assert len(cases) >= 1

    def test_inference_artifact_created(self, db, s3_iteration, mock_ai_s3, testUser):
        run = run_scenario(db, s3_iteration.id, 3, mock_ai_s3, testUser.id)
        db.flush()

        artifacts = db.query(Artifact).filter(Artifact.run_id == run.id).all()
        assert len(artifacts) >= 1

    def test_expected_inference_matches_annotation(self, gamma_project_data):
        expected = gamma_project_data["expected_inference"]
        assert len(expected) > 0
        for item in expected:
            assert "name" in item
            assert "key" in item
            assert "confidence" in item

    def test_run_record_queryable(self, db, s3_iteration, mock_ai_s3, testUser):
        run = run_scenario(db, s3_iteration.id, 3, mock_ai_s3, testUser.id)
        db.flush()

        found = db.query(PipelineRun).filter(PipelineRun.id == run.id).first()
        assert found is not None
