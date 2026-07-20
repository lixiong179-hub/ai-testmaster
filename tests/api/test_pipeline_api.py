"""Pipeline API 数据结构验证测试

覆盖范围:
    - pipeline_service.get_run 返回数据结构验证
    - steps 字段完整性（step_name/status/degraded/retried_count）
    - artifacts 字段完整性（kind/confidence/schema_version）
    - 不存在的 run_id 返回 None
    - run 基础字段（iteration_id/pipeline_version/input_hash）

使用真实 MySQL 数据库，复用 conftest 中的 testProject/testUser fixture。

注意:
    - TestPipelineRunStructure 使用同步 db（sync service 调用）
    - TestPipelineRunApi / TestScenario4Precheck 使用 async_db（async endpoint 调用）
      端点内部使用 db.run_sync / await db.execute，必须传入 AsyncSession。
"""
import pytest
from types import SimpleNamespace

# pytestmark = pytest.mark.skip(reason="数据库DDL不兼容")  # 临时移除排查

from app.models.iteration import Iteration
from app.models.test_point import TestPoint
from app.models.iteration import IterationInput
from app.models.pipeline import PipelineRun, PipelineStep, Artifact
from app.services import pipeline_service
from app.ai.mock_client import MockAIClient


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="pipeline_struct_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def test_run(db, test_iteration):
    run = pipeline_service.create_run(
        db=db,
        iteration_id=test_iteration.id,
        input_hash="struct_test_hash_001",
        pipeline_version="1.0",
    )
    db.flush()

    step1 = PipelineStep(
        run_id=run.id,
        step_name="signal_gatherer",
        step_version="1.0",
        status="done",
        retried_count=0,
        degraded=False,
    )
    db.add(step1)
    db.flush()

    step2 = PipelineStep(
        run_id=run.id,
        step_name="case_generation",
        step_version="1.0",
        status="running",
        retried_count=1,
        degraded=True,
    )
    db.add(step2)
    db.flush()

    artifact1 = Artifact(
        run_id=run.id,
        kind="raw_signals",
        schema_version="1.0",
        payload={"has_prd": True, "has_ui": False},
        confidence=0.85,
        content_hash="struct_test_artifact_001",
    )
    db.add(artifact1)
    db.flush()

    db.commit()
    db.refresh(run)
    return run


class TestPipelineRunStructure:
    def test_get_run_returns_run_object(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert run is not None
        assert run.id == test_run.id
        assert run.status in ("pending", "running", "completed", "failed", "waiting_for_user", "cancelled")

    def test_steps_are_accessible(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert len(run.steps) >= 1

    def test_step_fields_complete(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        step = run.steps[0]
        assert hasattr(step, "step_name")
        assert hasattr(step, "status")
        assert hasattr(step, "started_at")
        assert hasattr(step, "finished_at")
        assert hasattr(step, "error")
        assert hasattr(step, "retried_count")
        assert hasattr(step, "degraded")

    def test_step_degraded_flag(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        case_gen_steps = [s for s in run.steps if s.step_name == "case_generation"]
        assert len(case_gen_steps) == 1
        assert case_gen_steps[0].degraded is True
        assert case_gen_steps[0].retried_count == 1

    def test_step_done_status(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        sg_steps = [s for s in run.steps if s.step_name == "signal_gatherer"]
        assert len(sg_steps) == 1
        assert sg_steps[0].status == "done"
        assert sg_steps[0].degraded is False

    def test_artifacts_are_accessible(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert len(run.artifacts) >= 1

    def test_artifact_fields_complete(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        artifact = run.artifacts[0]
        assert hasattr(artifact, "kind")
        assert hasattr(artifact, "confidence")
        assert hasattr(artifact, "schema_version")
        assert hasattr(artifact, "created_at")

    def test_artifact_confidence_value(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        raw_signals = [a for a in run.artifacts if a.kind == "raw_signals"]
        assert len(raw_signals) == 1
        assert raw_signals[0].confidence == 0.85

    def test_nonexistent_run_returns_none(self, db):
        run = pipeline_service.get_run(db, 999999)
        assert run is None

    def test_run_has_iteration_id(self, db, test_run, test_iteration):
        run = pipeline_service.get_run(db, test_run.id)
        assert run.iteration_id == test_iteration.id

    def test_run_has_pipeline_version(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert run.pipeline_version == "1.0"

    def test_run_has_input_hash(self, db, test_run):
        run = pipeline_service.get_run(db, test_run.id)
        assert run.input_hash == "struct_test_hash_001"


@pytest.fixture
def runnable_iteration(db, testProject):
    from app.models.project import ProjectFile

    iteration = Iteration(
        project_id=testProject.id,
        name="pipeline_api_run_iter",
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

    # scenario=2 校验需要 PRD + testpoint；创建 PRD ProjectFile 满足 has_prd
    prd_file = ProjectFile(
        project_id=testProject.id,
        file_name="prd.docx",
        file_type="docx",
        file_url="/uploads/test/prd.docx",
        resource_type="requirement",
        content="PRD 内容：登录功能需求文档",
        extract_status="completed",
        is_active=True,
    )
    db.add(prd_file)
    db.flush()

    inp_tp = IterationInput(
        iteration_id=iteration.id,
        kind="testpoint",
        payload={"test_point_ids": [tp.id]},
        content_hash="pipeline_api_tp_hash",
    )
    db.add(inp_tp)

    inp_prd = IterationInput(
        iteration_id=iteration.id,
        kind="prd",
        file_id=prd_file.id,
        payload={"file_id": prd_file.id},
        content_hash="pipeline_api_prd_hash",
    )
    db.add(inp_prd)
    db.flush()
    return iteration


@pytest.fixture
def pipeline_api_mock_ai():
    client = MockAIClient()
    client.set_response("case_generation", """
    [
      {
        "title": "登录功能验证",
        "module": "用户管理",
        "precondition": "用户已注�?,
        "steps": [{"action": "输入用户名和密码", "expected": "登录成功"}],
        "expected_result": "成功登录",
        "priority": 1,
        "case_type": "functional"
      }
    ]
    """)
    return client


class TestPipelineRunApi:
    @pytest.mark.asyncio
    async def test_run_pipeline_returns_pipeline_run_id(
        self, db, sync_backed_async_db, testUser, runnable_iteration, pipeline_api_mock_ai, monkeypatch
    ):
        from app.api.v1.endpoints import pipeline as pipeline_endpoint

        monkeypatch.setattr(
            pipeline_endpoint,
            "_create_ai_client",
            lambda model_name=None: pipeline_api_mock_ai,
        )

        response = await pipeline_endpoint.run_pipeline(
            iteration_id=runnable_iteration.id,
            body=pipeline_endpoint.PipelineRunRequest(scenario=2),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )

        assert response["code"] == 200
        assert response["data"]["run_id"] == response["data"]["pipeline_run_id"]
        assert response["data"]["iteration_id"] == runnable_iteration.id


class TestScenario4Precheck:
    async def test_precheck_no_project_access(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest
        from fastapi import HTTPException
        import pytest as pytest_mod

        with pytest_mod.raises(HTTPException):
            await precheck_scenario_4(
                body=Scenario4PrecheckRequest(project_id=99999),
                db=sync_backed_async_db,
                current_user=SimpleNamespace(id=testUser.id),
            )

    async def test_precheck_empty_project(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest

        response = await precheck_scenario_4(
            body=Scenario4PrecheckRequest(project_id=testProject.id),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )
        assert response["code"] == 200
        data = response["data"]
        assert data["project_id"] == testProject.id
        assert data["history_cases"]["total"] == 0
        assert data["history_cases"]["included"] == 0
        assert data["can_run"] is False
        assert len(data["blocking_reasons"]) > 0

    async def test_precheck_with_history_cases(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.models.test_case import TestCase
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest

        tc1 = TestCase(
            project_id=testProject.id, title="用例1", lifecycle_status="active",
            is_deleted=False, case_no="TC-001", module="登录",
            precondition="前置条件", expected_result="预期结果", priority=1,
            case_type="API", steps_json=[],
        )
        tc2 = TestCase(
            project_id=testProject.id, title="用例2", lifecycle_status="draft",
            is_deleted=False, case_no="TC-002", module="登录",
            precondition="前置条件", expected_result="预期结果", priority=1,
            case_type="API", steps_json=[],
        )
        tc3 = TestCase(
            project_id=testProject.id, title="用例3", lifecycle_status="archived",
            is_deleted=False, case_no="TC-003", module="登录",
            precondition="前置条件", expected_result="预期结果", priority=1,
            case_type="API", steps_json=[],
        )
        tc4 = TestCase(
            project_id=testProject.id, title="用例4", lifecycle_status="active",
            is_deleted=True, case_no="TC-004", module="登录",
            precondition="前置条件", expected_result="预期结果", priority=1,
            case_type="API", steps_json=[],
        )
        db.add_all([tc1, tc2, tc3, tc4])
        db.flush()

        response = await precheck_scenario_4(
            body=Scenario4PrecheckRequest(project_id=testProject.id),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )
        data = response["data"]
        assert data["history_cases"]["total"] == 3
        assert data["history_cases"]["included"] == 2
        assert data["history_cases"]["active"] == 1
        assert data["history_cases"]["draft"] == 1
        assert data["history_cases"]["archived"] == 1

    async def test_precheck_with_test_points(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.models.test_point import TestPoint
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest

        tp1 = TestPoint(
            project_id=testProject.id, module="登录", point="登录功能",
            priority=1,
        )
        tp2 = TestPoint(
            project_id=testProject.id, module="注册", point="注册功能",
            priority=1,
        )
        db.add_all([tp1, tp2])
        db.flush()

        response = await precheck_scenario_4(
            body=Scenario4PrecheckRequest(
                project_id=testProject.id,
                test_point_ids=[tp1.id, tp2.id],
            ),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )
        data = response["data"]
        assert data["test_points"]["total"] == 2
        assert data["test_points"]["selected"] == 2

    async def test_precheck_test_points_wrong_project(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest
        from fastapi import HTTPException
        import pytest as pytest_mod

        with pytest_mod.raises(HTTPException):
            await precheck_scenario_4(
                body=Scenario4PrecheckRequest(
                    project_id=testProject.id,
                    test_point_ids=[99999],
                ),
                db=sync_backed_async_db,
                current_user=SimpleNamespace(id=testUser.id),
            )

    async def test_precheck_with_ui_screens(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest

        proto_project = UIPrototypeProject(
            project_id=testProject.id,
            name="测试原型项目",
        )
        db.add(proto_project)
        db.flush()

        s1 = UIPrototypeScreen(
            prototype_project_id=proto_project.id,
            project_id=testProject.id,
            prototype_name="首页原型",
            screen_name="首页", parse_status="completed",
            ui_spec={"elements": []}, screen_order=1,
        )
        s2 = UIPrototypeScreen(
            prototype_project_id=proto_project.id,
            project_id=testProject.id,
            prototype_name="设置页原型",
            screen_name="设置页", parse_status="pending",
            ui_spec=None, screen_order=2,
        )
        s3 = UIPrototypeScreen(
            prototype_project_id=proto_project.id,
            project_id=testProject.id,
            prototype_name="关于页原型",
            screen_name="关于页", parse_status="failed",
            ui_spec=None, screen_order=3,
        )
        db.add_all([s1, s2, s3])
        db.flush()

        response = await precheck_scenario_4(
            body=Scenario4PrecheckRequest(
                project_id=testProject.id,
                ui_project_id=proto_project.id,
            ),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )
        data = response["data"]
        assert data["ui"]["selected_screen_count"] == 3
        assert data["ui"]["parsed_screen_count"] == 1
        assert data["ui"]["unparsed_screen_count"] == 1
        assert data["ui"]["parse_failed_count"] == 1
        assert data["ui"]["usable_screen_ids"] == [s1.id]
        assert data["warnings"]

    async def test_precheck_without_ui_project_id(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest

        response = await precheck_scenario_4(
            body=Scenario4PrecheckRequest(project_id=testProject.id),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )
        data = response["data"]
        assert data["ui"]["selected_screen_count"] == 0

    async def test_precheck_cannot_access_ui_project(
        self, db, sync_backed_async_db, testUser, testProject
    ):
        from app.api.v1.endpoints.pipeline import precheck_scenario_4, Scenario4PrecheckRequest
        from fastapi import HTTPException
        import pytest as pytest_mod

        with pytest_mod.raises(HTTPException):
            await precheck_scenario_4(
                body=Scenario4PrecheckRequest(
                    project_id=testProject.id,
                    ui_project_id=99999,
                ),
                db=sync_backed_async_db,
                current_user=SimpleNamespace(id=testUser.id),
            )

    @pytest.mark.asyncio
    async def test_compatible_iteration_route_returns_pipeline_run_id(
        self, db, sync_backed_async_db, testUser, runnable_iteration, pipeline_api_mock_ai, monkeypatch
    ):
        from app.api.v1.endpoints import pipeline as pipeline_endpoint
        from app.api.v1.endpoints import iteration as iteration_endpoint

        monkeypatch.setattr(
            pipeline_endpoint,
            "_create_ai_client",
            lambda model_name=None: pipeline_api_mock_ai,
        )

        response = await iteration_endpoint.run_iteration_pipeline(
            iteration_id=runnable_iteration.id,
            body=pipeline_endpoint.PipelineRunRequest(scenario=2),
            db=sync_backed_async_db,
            current_user=SimpleNamespace(id=testUser.id),
        )

        assert response["code"] == 200
        assert response["data"]["run_id"] == response["data"]["pipeline_run_id"]
        assert response["data"]["iteration_id"] == runnable_iteration.id
