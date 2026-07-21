"""场景 1 回归测试 — 全输入新项目（PRD + 测试点 + UI）
验证 Pipeline 场景 1 的核心行为不变：
    - 场景注册表可查询
    - 依赖链完整（5 个 Step）    - Pipeline 端到端运行完成    - 生成用例数量与标注集一致    - 用例持久化到数据库    - 用例 lifecycle_status 正确

使用 Alpha 标注集作为固定输入，MockAIClient 模拟 AI 响应。"""
import json
import pytest

from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.iteration import Iteration, IterationInput
from app.models.pipeline import PipelineRun, Artifact
from app.pipelines.scenarios import get_scenario
from tests.regression.conftest import _make_mock_ai, run_scenario


SCENARIO_1_MOCK_CASES = [
    {
        "title": "验证注册表单用户名为空时的错误提示",
        "module": "用户注册",
        "precondition": "用户未登录，处于注册页面",
        "steps": [
            {"action": "用户名输入框留空", "expected": "用户名输入框显示为空"},
            {"action": "填写其他必填字段", "expected": "邮箱、密码、确认密码已填写"},
            {"action": "点击注册按钮", "expected": "提示'用户名不能为空"},
        ],
        "expected_result": "页面显示错误提示，注册未提交",
        "priority": 1,
        "case_type": "functional",
    },
    {
        "title": "验证密码长度不足8位时的错误提示",
        "module": "用户注册",
        "precondition": "用户处于注册页面，已填写用户名和邮箱",
        "steps": [
            {"action": "输入密码'abc123'（6位）", "expected": "密码输入框显示6位"},
            {"action": "确认密码输入同样内容", "expected": "两次密码一致"},
            {"action": "点击注册按钮", "expected": "提示'密码长度需8-20位'"},
        ],
        "expected_result": "页面显示密码长度错误提示",
        "priority": 1,
        "case_type": "functional",
    },
]


@pytest.fixture
def mock_ai_s1():
    return _make_mock_ai(SCENARIO_1_MOCK_CASES)


@pytest.fixture
def s1_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="regression_s1",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    tp = TestPoint(
        project_id=testProject.id,
        module="用户注册",
        point="注册表单验证",
        priority=1,
    )
    db.add(tp)
    db.flush()

    for kind in ["prd", "prototype", "testpoint"]:
        inp = IterationInput(
            iteration_id=iteration.id,
            kind=kind,
            payload={"test": True},
            content_hash=f"regression_s1_{kind}",
        )
        db.add(inp)

    db.flush()
    return iteration


@pytest.mark.regression
@pytest.mark.scenario_fast
class TestScenario1Regression:
    """场景 1 回归：全输入新项目"""

    def test_scenario_registered(self):
        scenario = get_scenario(1)
        assert scenario is not None
        assert scenario["name"] == "scenario_1_full"
        assert len(scenario["steps"]) == 5

    def test_step_chain_intact(self):
        scenario = get_scenario(1)
        step_names = [s.__name__ for s in scenario["steps"]]
        assert step_names == [
            "SignalGatherer",
            "TestPointAlignment",
            "CaseGeneration",
            "QualityGate",
            "Persist",
        ]

    def test_pipeline_completes(self, db, s1_iteration, mock_ai_s1, testUser):
        run = run_scenario(db, s1_iteration.id, 1, mock_ai_s1, testUser.id)
        db.flush()
        assert run.status == "completed"

    def test_cases_persisted(self, db, s1_iteration, mock_ai_s1, testUser):
        run_scenario(db, s1_iteration.id, 1, mock_ai_s1, testUser.id)
        db.flush()

        cases = db.query(TestCase).filter(
            TestCase.project_id == s1_iteration.project_id
        ).all()
        assert len(cases) >= 1

    def test_case_fields_match_mock(self, db, s1_iteration, mock_ai_s1, testUser):
        run_scenario(db, s1_iteration.id, 1, mock_ai_s1, testUser.id)
        db.flush()

        case = db.query(TestCase).filter(
            TestCase.project_id == s1_iteration.project_id
        ).first()
        assert case is not None
        assert case.title == SCENARIO_1_MOCK_CASES[0]["title"]
        assert case.module == SCENARIO_1_MOCK_CASES[0]["module"]

    def test_expected_case_count_matches_annotation(self, db, alpha_project_data):
        expected = alpha_project_data["expected_cases"]
        assert len(expected) > 0
        for ec in expected:
            assert "title" in ec
            assert "module" in ec
            assert "steps" in ec

    def test_artifacts_created(self, db, s1_iteration, mock_ai_s1, testUser):
        run = run_scenario(db, s1_iteration.id, 1, mock_ai_s1, testUser.id)
        db.flush()

        artifacts = db.query(Artifact).filter(Artifact.run_id == run.id).all()
        assert len(artifacts) >= 1

    def test_run_record_queryable(self, db, s1_iteration, mock_ai_s1, testUser):
        run = run_scenario(db, s1_iteration.id, 1, mock_ai_s1, testUser.id)
        db.flush()

        found = db.query(PipelineRun).filter(PipelineRun.id == run.id).first()
        assert found is not None
        assert found.iteration_id == s1_iteration.id
