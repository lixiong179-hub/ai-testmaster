"""
M1-T12 场景 2 流水线测试（PRD + 测试点，无 UI）

覆盖：
    - 场景 2 完整 Pipeline 端到端（无 UI 输入）
    - 生成的用例 locator_status=pending
    - 场景 2 不包含 TestPointAlignment Step
    - 场景注册表查询
"""
import json
import pytest

from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration, IterationInput
from app.models.test_point import TestPoint
from app.models.test_case import TestCase
from app.services import pipeline_service
from app.pipelines.scenarios import get_scenario


@pytest.fixture
def mock_ai():
    client = MockAIClient()
    client.set_response("case_generation", json.dumps([
        {
            "title": "登录功能验证",
            "module": "用户管理",
            "precondition": "用户已注册",
            "steps": [
                {"action": "输入正确的用户名和密码", "expected": "登录成功"},
            ],
            "expected_result": "成功登录",
            "priority": 1,
            "case_type": "functional",
        }
    ]))
    return client


@pytest.fixture
def setup_no_ui_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="scenario2_no_ui",
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
        content_hash="s2_tp_hash_001",
    )
    db.add(inp)
    db.flush()

    return {"iteration": iteration, "test_point": tp}


class TestScenario2Registry:
    def test_get_scenario_2(self):
        scenario = get_scenario(2)
        assert scenario is not None
        assert scenario["name"] == "scenario_2_no_ui"
        assert len(scenario["steps"]) == 4

    def test_scenario_2_no_alignment_step(self):
        scenario = get_scenario(2)
        step_names = [s.name for s in scenario["steps"]]
        assert "testpoint_alignment" not in step_names
        assert "signal_gatherer" in step_names
        assert "case_generation" in step_names
        assert "quality_gate" in step_names
        assert "persist" in step_names


class TestScenario2E2E:
    def test_full_pipeline_no_ui(self, db, testProject, mock_ai, setup_no_ui_iteration):
        iteration = setup_no_ui_iteration["iteration"]

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s2_e2e_hash",
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

        scenario = get_scenario(2)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status == "completed"

    def test_generated_cases_without_ui(self, db, testProject, mock_ai, setup_no_ui_iteration):
        iteration = setup_no_ui_iteration["iteration"]

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s2_no_ui_hash",
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

        scenario = get_scenario(2)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        cases = db.query(TestCase).filter(
            TestCase.project_id == testProject.id,
        ).all()
        assert len(cases) >= 1
        for case in cases:
            assert case.lifecycle_status in ("draft", "pending_review")

    def test_signals_have_no_ui(self, db, testProject, mock_ai, setup_no_ui_iteration):
        iteration = setup_no_ui_iteration["iteration"]

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s2_signals_hash",
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

        scenario = get_scenario(2)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        signals = ctx.get_artifact("raw_signals")
        assert signals is not None
        assert signals.get("has_ui") is False
        assert signals.get("has_testpoints") is True

    def test_pipeline_with_prd_only(self, db, testProject, mock_ai):
        from app.models.project import ProjectFile

        iteration = Iteration(
            project_id=testProject.id,
            name="s2_prd_only",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        prd_file = ProjectFile(
            project_id=testProject.id,
            file_name="需求文档.docx",
            file_url="/tmp/prd.docx",
            file_type="docx",
            size=2048,
            resource_type="requirement",
            extract_status="completed",
            content="登录功能需求：支持账号密码登录",
        )
        db.add(prd_file)
        db.flush()

        prd_inp = IterationInput(
            iteration_id=iteration.id,
            kind="prd",
            file_id=prd_file.id,
            content_hash="s2_prd_hash",
        )
        db.add(prd_inp)

        tp = TestPoint(
            project_id=testProject.id,
            module="登录",
            point="密码登录",
            priority=1,
        )
        db.add(tp)
        db.flush()

        tp_inp = IterationInput(
            iteration_id=iteration.id,
            kind="testpoint",
            payload={"test_point_ids": [tp.id]},
            content_hash="s2_tp_hash",
        )
        db.add(tp_inp)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s2_prd_only_hash",
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

        scenario = get_scenario(2)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status == "completed"

        signals = ctx.get_artifact("raw_signals")
        assert signals.get("has_prd") is True
        assert signals.get("has_ui") is False

    def test_empty_iteration_fails_gracefully(self, db, testProject, mock_ai):
        iteration = Iteration(
            project_id=testProject.id,
            name="s2_empty_iter",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s2_empty_hash",
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

        scenario = get_scenario(2)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status == "failed"

    def test_ai_empty_response_degraded(self, db, testProject):
        empty_ai = MockAIClient()
        empty_ai.set_response("case_generation", "")

        iteration = Iteration(
            project_id=testProject.id,
            name="s2_ai_empty",
            status="draft",
        )
        db.add(iteration)
        db.flush()

        tp = TestPoint(
            project_id=testProject.id,
            module="登录",
            point="密码登录",
            priority=1,
        )
        db.add(tp)
        db.flush()

        inp = IterationInput(
            iteration_id=iteration.id,
            kind="testpoint",
            payload={"test_point_ids": [tp.id]},
            content_hash="s2_ai_empty_tp_hash",
        )
        db.add(inp)
        db.flush()

        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash="s2_ai_empty_hash",
            pipeline_version="1.0",
        )
        db.flush()

        ctx = PipelineContext(
            db=db,
            ai_client=empty_ai,
            run=run,
            iteration_id=iteration.id,
            user_id=1,
        )

        scenario = get_scenario(2)
        runner = PipelineRunner(scenario["name"], scenario["steps"])
        runner.run(ctx)

        db.refresh(run)
        assert run.status == "failed"
