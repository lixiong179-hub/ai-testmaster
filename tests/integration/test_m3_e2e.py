"""M3 集成测试 �?场景 3 + 场景 5 端到端验�?

覆盖范围:
    - 场景 3（仅 UI 新项目）：完�?Pipeline 跑通，反推能力 �?候选场�?�?对齐 �?生成用例
    - 场景 5（旧项目无新 PRD）：历史反推 + 双向扫描 + Reconciliation �?变更用例
    - 产物验证（inferred_capabilities / scenario_candidates / backward_verdicts / merged_verdicts�?
    - 用例持久化验证（lifecycle_status / case_type�?
    - 场景注册�?1-5 完整性验�?

使用真实 MySQL 数据�?+ MockAIClient，不使用 FastAPI TestClient�?
"""
import json
import pytest

from app.models.iteration import Iteration, IterationInput
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.ai.mock_client import MockAIClient
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.scenarios import get_scenario
from app.services import pipeline_service


SCENARIO_3_CASES = [
    {
        "title": "验证登录页面用户名密码登�?,
        "module": "用户登录",
        "precondition": "用户已注�?,
        "steps": [
            {"action": "打开登录页面", "expected": "显示登录表单"},
            {"action": "输入用户名和密码", "expected": "输入内容已填�?},
            {"action": "点击登录按钮", "expected": "登录成功，跳转首�?},
        ],
        "expected_result": "成功登录并跳转至首页",
        "priority": 1,
        "case_type": "functional",
    },
]

SCENARIO_5_CASES = [
    {
        "title": "历史用例变更验证",
        "module": "用户注册",
        "precondition": "用户已注�?,
        "steps": [
            {"action": "验证新注册流�?, "expected": "手机号验证码流程正常"},
        ],
        "expected_result": "变更后注册流程可�?,
        "priority": 1,
        "case_type": "functional",
    },
]


def _make_artifact(kind: str, payload: dict):
    from app.models.pipeline import Artifact
    return Artifact(run_id=0, kind=kind, schema_version="1.0", payload=payload, content_hash="test")


@pytest.fixture
def mock_ai_s3():
    client = MockAIClient()
    client.set_response("reverse_infer", json.dumps({
        "inferred_capabilities": [
            {
                "name": "用户登录",
                "key": "user_login",
                "description": "用户通过用户名和密码登录系统",
                "confidence": 0.9,
            },
            {
                "name": "用户注册",
                "key": "user_registration",
                "description": "新用户通过填写表单创建账号",
                "confidence": 0.85,
            },
        ],
        "overall_confidence": 0.87,
        "uncertain_questions": [],
    }))
    client.set_response("scenario_candidate_extractor", json.dumps({
        "candidates": [
            {
                "description": "用户登录场景",
                "module": "用户登录",
                "precondition": "用户已注�?,
                "expected_result": "成功登录",
            },
        ],
    }))
    client.set_response("case_generation", json.dumps(SCENARIO_3_CASES))
    return client


@pytest.fixture
def mock_ai_s5():
    client = MockAIClient()
    client.set_response("reverse_infer", json.dumps({
        "change_summary": {
            "new_capabilities": [
                {
                    "name": "手机号验�?,
                    "key": "phone_verification",
                    "description": "用户注册时需短信验证码验证手机号",
                    "confidence": 0.88,
                },
            ],
            "modified_capabilities": [
                {
                    "name": "用户注册",
                    "key": "user_registration",
                    "description": "注册流程新增手机号必填和短信验证",
                    "confidence": 0.85,
                },
            ],
            "removed_capabilities": [],
        },
        "overall_confidence": 0.88,
        "uncertain_questions": [],
    }))
    client.set_response("scenario_candidate_extractor", json.dumps({
        "candidates": [
            {
                "description": "注册流程变更验证",
                "module": "用户注册",
                "precondition": "",
                "expected_result": "变更后正�?,
            },
        ],
    }))
    client.set_response("case_generation", json.dumps(SCENARIO_5_CASES))
    return client


@pytest.fixture
def s3_iteration(db, testProject):
    from app.models.ui_prototype import UIPrototypeScreen

    screen = UIPrototypeScreen(
        project_id=testProject.id,
        prototype_name="m3_proto",
        screen_name="登录�?,
        source="manual",
        screen_order=0,
        parse_status="completed",
        summary="登录页面，包含用户名密码输入框和登录按钮",
        ui_spec={
            "components": [
                {"type": "input", "label": "用户�?},
                {"type": "input", "label": "密码", "input_type": "password"},
                {"type": "button", "label": "登录"},
            ]
        },
    )
    db.add(screen)
    db.flush()

    iteration = Iteration(project_id=testProject.id, name="m3_e2e_s3", status="draft")
    db.add(iteration)
    db.flush()

    ui_input = IterationInput(
        iteration_id=iteration.id,
        kind="prototype",
        payload={"ui_prototype_id": 1},
        content_hash="m3_e2e_s3_ui_hash",
    )
    db.add(ui_input)
    db.flush()
    return {"iteration": iteration}


@pytest.fixture
def s5_iteration(db, testProject):
    from app.models.ui_prototype import UIPrototypeScreen

    screen = UIPrototypeScreen(
        project_id=testProject.id,
        prototype_name="m3_s5_proto",
        screen_name="注册�?,
        source="manual",
        screen_order=0,
        parse_status="completed",
        summary="注册页面，含手机号验证码",
        ui_spec={
            "components": [
                {"type": "input", "label": "用户�?},
                {"type": "input", "label": "邮箱"},
                {"type": "input", "label": "手机�?},
                {"type": "input", "label": "密码", "input_type": "password"},
                {"type": "button", "label": "获取验证�?},
                {"type": "button", "label": "注册"},
            ]
        },
    )
    db.add(screen)
    db.flush()

    enable_lifecycle_transition()
    try:
        for i in range(3):
            case = TestCase(
                project_id=testProject.id,
                case_no=f"S5-HIST-{i:03d}",
                title=f"历史用例 {i} �?用户注册模块",
                module="用户注册",
                precondition="",
                steps_json=[{"action": "操作", "expected": "预期"}],
                expected_result="通过",
                priority=1,
                case_type="functional",
                lifecycle_status="active",
                summary=f"历史注册用例 {i}",
            )
            db.add(case)
        db.flush()
    finally:
        disable_lifecycle_transition()

    iteration = Iteration(project_id=testProject.id, name="m3_e2e_s5", status="draft")
    db.add(iteration)
    db.flush()

    ui_input = IterationInput(
        iteration_id=iteration.id,
        kind="prototype",
        payload={"ui_prototype_id": 2},
        content_hash="m3_e2e_s5_ui_hash",
    )
    db.add(ui_input)
    db.flush()
    return {"iteration": iteration}


def _run_s3_pipeline(db, iteration, mock_ai):
    run = pipeline_service.create_run(
        db=db, iteration_id=iteration.id,
        input_hash="m3_e2e_s3_hash", pipeline_version="3.0",
    )
    db.flush()

    ctx = PipelineContext(db=db, ai_client=mock_ai, run=run, iteration_id=iteration.id, user_id=1)
    scenario = get_scenario(3)
    runner = PipelineRunner(scenario["name"], scenario["steps"])
    runner.run(ctx)
    db.refresh(run)
    return run, ctx


def _setup_scenario_5_mocks(ctx, mock_ai):
    from app.pipelines.steps.history_fingerprint import HistoryFingerprint
    from app.pipelines.steps.signal_gatherer import SignalGatherer

    gatherer = SignalGatherer()
    g_result = gatherer.execute(ctx)
    ctx.set_artifact("raw_signals", _make_artifact("raw_signals", g_result.artifact_payload))

    f_step = HistoryFingerprint()
    f_result = f_step.execute(ctx)
    ctx.set_artifact("history_fingerprints", _make_artifact("history_fingerprints", f_result.artifact_payload))

    fps = f_result.artifact_payload.get("fingerprints", [])
    verdicts = []
    for i, fp in enumerate(fps):
        verdict = "VALID" if i % 3 == 0 else ("NEEDS_MODIFY" if i % 3 == 1 else "DEPRECATED")
        verdicts.append({"case_id": fp["case_id"], "verdict": verdict, "confidence": 0.9, "hint": "自动判定"})
    mock_ai.set_response("backward_scan", json.dumps({"verdicts": verdicts}))
    mock_ai.set_response("forward_scan", json.dumps({
        "label": "MODIFY", "matched_case_id": fps[0]["case_id"], "matched_title": "",
        "confidence": 0.85, "reason": "变更适配",
    }))


def _run_s5_pipeline(db, iteration, mock_ai):
    run = pipeline_service.create_run(
        db=db, iteration_id=iteration.id,
        input_hash="m3_e2e_s5_hash", pipeline_version="5.0",
    )
    db.flush()

    ctx = PipelineContext(db=db, ai_client=mock_ai, run=run, iteration_id=iteration.id, user_id=1)
    _setup_scenario_5_mocks(ctx, mock_ai)

    scenario = get_scenario(5)
    runner = PipelineRunner(scenario["name"], scenario["steps"])
    runner.run(ctx)
    db.refresh(run)
    return run, ctx


class TestScenario3E2E:
    def test_pipeline_completes(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        run, _ = _run_s3_pipeline(db, iteration, mock_ai_s3)
        assert run.status == "completed"

    def test_produces_inferred_capabilities(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        _, ctx = _run_s3_pipeline(db, iteration, mock_ai_s3)

        artifact = ctx.get_artifact("inferred_business_summary")
        assert artifact is not None
        assert "parsed" in artifact
        caps = artifact["parsed"].get("inferred_capabilities", [])
        assert len(caps) >= 2
        assert artifact.get("confidence", 0) >= 0.7

    def test_produces_scenario_candidates(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        _, ctx = _run_s3_pipeline(db, iteration, mock_ai_s3)

        candidates = ctx.get_artifact("scenario_candidates")
        assert candidates is not None
        assert "candidates" in candidates
        assert len(candidates["candidates"]) >= 1

    def test_generates_cases(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        _, ctx = _run_s3_pipeline(db, iteration, mock_ai_s3)

        cases = ctx.get_artifact("generated_cases")
        assert cases is not None
        assert len(cases) >= 1

    def test_cases_persisted(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        _run_s3_pipeline(db, iteration, mock_ai_s3)

        db_cases = db.query(TestCase).filter(
            TestCase.project_id == iteration.project_id,
        ).all()
        assert len(db_cases) >= 1
        for case in db_cases:
            assert case.lifecycle_status in ("draft", "pending_review")
            assert case.case_type in ("functional", "UI")

    def test_signals_ui_only(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        _, ctx = _run_s3_pipeline(db, iteration, mock_ai_s3)

        signals = ctx.get_artifact("raw_signals")
        assert signals is not None
        assert signals.get("has_ui") is True

    def test_run_record_queryable(self, db, s3_iteration, mock_ai_s3):
        iteration = s3_iteration["iteration"]
        run, _ = _run_s3_pipeline(db, iteration, mock_ai_s3)

        found = pipeline_service.get_run(db, run.id)
        assert found is not None
        assert found.status == "completed"
        assert len(found.steps) >= 6
        assert len(found.artifacts) >= 1


class TestScenario5E2E:
    def test_pipeline_completes(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        run, _ = _run_s5_pipeline(db, iteration, mock_ai_s5)
        assert run.status == "completed"

    def test_produces_history_fingerprints(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _, ctx = _run_s5_pipeline(db, iteration, mock_ai_s5)

        fingerprints = ctx.get_artifact("history_fingerprints")
        assert fingerprints is not None
        assert fingerprints.get("total_count") >= 3

    def test_produces_inferred_capabilities(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _, ctx = _run_s5_pipeline(db, iteration, mock_ai_s5)

        artifact = ctx.get_artifact("inferred_business_summary")
        assert artifact is not None
        assert "parsed" in artifact
        cs = artifact["parsed"].get("change_summary", {})
        assert len(cs.get("new_capabilities", [])) + len(cs.get("modified_capabilities", [])) >= 1

    def test_produces_backward_verdicts(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _, ctx = _run_s5_pipeline(db, iteration, mock_ai_s5)

        backward = ctx.get_artifact("backward_verdicts")
        assert backward is not None

    def test_produces_merged_verdicts(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _, ctx = _run_s5_pipeline(db, iteration, mock_ai_s5)

        merged = ctx.get_artifact("merged_verdicts")
        assert merged is not None

    def test_generates_cases(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _, ctx = _run_s5_pipeline(db, iteration, mock_ai_s5)

        cases = ctx.get_artifact("generated_cases")
        assert cases is not None
        assert len(cases) >= 1

    def test_cases_persisted(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _run_s5_pipeline(db, iteration, mock_ai_s5)

        db_cases = db.query(TestCase).filter(
            TestCase.project_id == iteration.project_id,
        ).all()
        assert len(db_cases) >= 3

    def test_signals_reflect_old_project(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        _, ctx = _run_s5_pipeline(db, iteration, mock_ai_s5)

        signals = ctx.get_artifact("raw_signals")
        assert signals is not None
        assert signals.get("is_old_project") is True

    def test_run_record_queryable(self, db, s5_iteration, mock_ai_s5):
        iteration = s5_iteration["iteration"]
        run, _ = _run_s5_pipeline(db, iteration, mock_ai_s5)

        found = pipeline_service.get_run(db, run.id)
        assert found is not None
        assert found.status == "completed"
        assert len(found.steps) >= 8
        assert len(found.artifacts) >= 1


class TestM3CrossScenario:
    def test_scenario_registry_complete(self):
        for sid in [1, 2, 3, 4, 5]:
            scenario = get_scenario(sid)
            assert scenario is not None, f"Scenario {sid} missing"
            assert "name" in scenario, f"Scenario {sid} missing name"
            assert "steps" in scenario, f"Scenario {sid} missing steps"
            assert len(scenario["steps"]) >= 3, f"Scenario {sid} has {len(scenario['steps'])} steps, min 3"

    def test_all_scenarios_registered(self):
        scenarios = [1, 2, 3, 4, 5]
        for sid in scenarios:
            assert get_scenario(sid) is not None, f"场景 {sid} 未注�?

    def test_scenario_3_registered(self):
        s3 = get_scenario(3)
        assert s3 is not None
        assert s3["name"] == "scenario_3_ui_only"
        assert s3["version"] == "3.0"
        step_names = [s.name for s in s3["steps"]]
        assert "reverse_infer" in step_names
        assert "scenario_candidate_extractor" in step_names

    def test_scenario_5_registered(self):
        s5 = get_scenario(5)
        assert s5 is not None
        assert s5["name"] == "scenario_5_old_project_no_prd"
        assert s5["version"] == "5.0"
        step_names = [s.name for s in s5["steps"]]
        assert "reverse_infer" in step_names
        assert "reconciliation" in step_names
        assert "history_fingerprint" in step_names
