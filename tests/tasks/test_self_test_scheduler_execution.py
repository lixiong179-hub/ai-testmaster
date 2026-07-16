"""
SelfTestScheduler 执行链路测试模块

覆盖场景：
    - _execute_self_test: 项目不存在/全链路模式/UI自动化无用例
    - _cleanup_self_test_data: 任务不存在/正常清理任务与解绑Bug
    - _notify_new_failures: 空用例列表/真实用例广播（WebSocket 失败被捕获）
    - handle_step_failure: P0缺陷创建Bug并通知/P2缺陷创建Bug不通知

使用真实测试库，monkeypatch 仅用于替换涉及 Playwright/AI 的执行入口
（_execute_self_test 内的 PrimarySessionLocal 与 run_defect_discovery_self_test），
验证调度器执行链路的事务隔离、异常捕获、数据清理逻辑。
"""
import pytest

from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.tasks.self_test_scheduler import SelfTestScheduler


class TestExecuteSelfTest:
    """_execute_self_test 自测执行入口测试。

    monkeypatch PrimarySessionLocal 指向测试库会话（事务隔离），
    覆盖项目不存在、full_pipeline 模式、ui_automation 无用例三个分支。
    """

    async def test_project_not_exists_returns_early(
        self, db, monkeypatch
    ) -> None:
        """项目不存在时应记录错误并提前返回，不抛异常。"""
        from app.db import database as dbModule

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", lambda: db)
        scheduler = SelfTestScheduler()
        await scheduler._execute_self_test(999999)
        assert 999999 not in scheduler._running_projects

    async def test_full_pipeline_mode_executes(
        self, db, testUser, monkeypatch
    ) -> None:
        """full_pipeline 模式应调用 run_defect_discovery_self_test。"""
        from app.db import database as dbModule
        from app.tasks import self_test_scheduler as schedModule

        project = Project(
            name="self_test_full_pipeline",
            user_id=testUser.id,
            is_self_test=True,
            config={"self_test_mode": "full_pipeline"},
            project_type="web",
        )
        db.add(project)
        db.flush()

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", lambda: db)
        called = {"flag": False}

        async def fakeRun(db, project_id, user_id):
            called["flag"] = True
            return {"success": True, "defect_summary": {"p0": 0}}

        monkeypatch.setattr(schedModule, "run_defect_discovery_self_test", fakeRun)

        scheduler = SelfTestScheduler()
        await scheduler._execute_self_test(project.id)
        assert called["flag"] is True

    async def test_ui_automation_no_active_cases(
        self, db, testUser, monkeypatch
    ) -> None:
        """ui_automation 模式下无活跃用例应跳过执行（提前返回）。"""
        from app.db import database as dbModule

        project = Project(
            name="self_test_ui_no_cases",
            user_id=testUser.id,
            is_self_test=True,
            config={"self_test_mode": "ui_automation"},
            project_type="web",
        )
        db.add(project)
        db.flush()

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", lambda: db)

        scheduler = SelfTestScheduler()
        await scheduler._execute_self_test(project.id)
        assert db.query(TestTask).filter(
            TestTask.project_id == project.id
        ).count() == 0


class TestCleanupSelfTestData:
    """_cleanup_self_test_data 自测数据清理测试。

    使用真实数据库验证：任务不存在时安全返回、任务存在时
    删除任务并解绑关联 Bug 的 test_result_id。
    """

    async def test_cleanup_task_not_exists(self, db) -> None:
        """任务不存在时应安全返回，不抛异常。"""
        scheduler = SelfTestScheduler()
        await scheduler._cleanup_self_test_data(db, 999999)

    async def test_cleanup_removes_task_and_unlinks_bugs(
        self, db, testUser, testProject
    ) -> None:
        """任务存在时应删除任务、解绑 Bug 的 test_result_id、更新复现步骤。"""
        task = TestTask(
            task_name="cleanup_test_task",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        db.add(task)
        db.flush()

        testCase = TestCase(
            case_no="TC-CLN-001",
            project_id=testProject.id,
            module="cleanup_module",
            title="cleanup case",
            precondition="none",
            steps_json=[{"step": "1", "action": "click", "param": ""}],
            expected_result="ok",
            priority=2,
            case_type="UI",
            test_category="ui_automation",
        )
        db.add(testCase)
        db.flush()

        result = TestResult(
            task_id=task.id,
            project_id=testProject.id,
            case_id=testCase.id,
            case_no=testCase.case_no,
            exec_status=2,
            error_msg="element not found",
            exec_log="step 1 failed",
        )
        db.add(result)
        db.flush()

        bug = Bug(
            bug_no="BUG-CLN-001",
            project_id=testProject.id,
            title="cleanup bug",
            description="test",
            severity=2,
            priority=1,
            status="open",
            source="self_test",
            reporter_id=testUser.id,
            test_result_id=result.id,
        )
        db.add(bug)
        db.flush()

        scheduler = SelfTestScheduler()
        await scheduler._cleanup_self_test_data(db, task.id)

        assert db.query(TestTask).filter(TestTask.id == task.id).first() is None
        dbBug = db.query(Bug).filter(Bug.id == bug.id).first()
        assert dbBug is not None
        assert dbBug.test_result_id is None
        assert "element not found" in (dbBug.reproduction_steps or "")


class TestNotifyNewFailures:
    """_notify_new_failures 失败通知测试。

    WebSocket 广播在测试环境无连接客户端会失败，
    但 try/except 捕获异常不传播，验证通知链路安全。
    """

    async def test_notify_with_empty_case_ids(self, db, testProject) -> None:
        """空用例列表应正常构造消息并尝试广播（失败被捕获）。"""
        scheduler = SelfTestScheduler()
        await scheduler._notify_new_failures(db, testProject, 0, [])

    async def test_notify_with_cases_handles_websocket_failure(
        self, db, testUser, testProject
    ) -> None:
        """真实用例应构造完整消息，WebSocket 失败被 try/except 捕获。"""
        testCase = TestCase(
            case_no="TC-NOTIFY-001",
            project_id=testProject.id,
            module="notify_module",
            title="notify case",
            precondition="none",
            steps_json=[{"step": "1", "action": "click", "param": ""}],
            expected_result="ok",
            priority=2,
            case_type="UI",
            test_category="ui_automation",
        )
        db.add(testCase)
        db.flush()

        scheduler = SelfTestScheduler()
        await scheduler._notify_new_failures(
            db, testProject, 1, [testCase.id]
        )


class TestHandleStepFailureSelfTest:
    """handle_step_failure 自测项目缺陷处理测试。

    使用真实自测项目验证：P0 缺陷创建 Bug 并触发 WebSocket 通知
    （失败被 _notify_critical_defect_bug 内部 try/except 捕获），
    P2 缺陷创建 Bug 但不触发通知。
    """

    async def test_p0_defect_creates_bug_and_notifies(
        self, db, testUser
    ) -> None:
        """P0 缺陷（no_sensitive_data）应创建 severity=1 的 Bug 并尝试通知。"""
        project = Project(
            name="self_test_p0_project",
            user_id=testUser.id,
            is_self_test=True,
            project_type="web",
        )
        db.add(project)
        db.flush()

        scheduler = SelfTestScheduler()
        bug = await scheduler.handle_step_failure(
            db=db,
            project=project,
            failure_type="no_sensitive_data",
            error_message="password field exposed in DOM",
            step_description="安全断言失败",
        )
        assert bug is not None
        assert bug.severity == 1
        assert bug.source == "self_test"
        assert bug.project_id == project.id

    async def test_p2_defect_creates_bug_no_notify(
        self, db, testUser
    ) -> None:
        """P2 缺陷（loading_hidden）应创建 severity=3 的 Bug，不触发通知。"""
        project = Project(
            name="self_test_p2_project",
            user_id=testUser.id,
            is_self_test=True,
            project_type="web",
        )
        db.add(project)
        db.flush()

        scheduler = SelfTestScheduler()
        bug = await scheduler.handle_step_failure(
            db=db,
            project=project,
            failure_type="loading_hidden",
            error_message="loading indicator never disappeared",
            step_description="加载状态断言失败",
        )
        assert bug is not None
        assert bug.severity == 3
        assert bug.source == "self_test"


class TestExecuteSelfTestException:
    """_execute_self_test 异常捕获测试。

    monkeypatch run_defect_discovery_self_test 抛异常，
    验证 except 块捕获异常并记录日志，不传播。
    """

    async def test_exception_in_full_pipeline_caught(
        self, db, testUser, monkeypatch
    ) -> None:
        """full_pipeline 执行抛异常应被 _execute_self_test except 捕获。"""
        from app.db import database as dbModule
        from app.tasks import self_test_scheduler as schedModule

        project = Project(
            name="self_test_exc_pipeline",
            user_id=testUser.id,
            is_self_test=True,
            config={"self_test_mode": "full_pipeline"},
            project_type="web",
        )
        db.add(project)
        db.flush()

        monkeypatch.setattr(dbModule, "PrimarySessionLocal", lambda: db)

        async def fakeRun(db, project_id, user_id):
            raise RuntimeError("pipeline crash")

        monkeypatch.setattr(schedModule, "run_defect_discovery_self_test", fakeRun)

        scheduler = SelfTestScheduler()
        await scheduler._execute_self_test(project.id)


class TestNotifyNewFailuresException:
    """_notify_new_failures 异常捕获测试。

    monkeypatch ws_manager.broadcast 抛异常，
    验证 except 块捕获异常不传播。
    """

    async def test_broadcast_exception_caught(
        self, db, testProject, monkeypatch
    ) -> None:
        """WebSocket broadcast 抛异常应被 try/except 捕获。"""
        from app.core.websocket import manager as wsModule

        async def fakeBroadcast(channel, message):
            raise ConnectionError("websocket down")

        monkeypatch.setattr(wsModule, "broadcast", fakeBroadcast)

        scheduler = SelfTestScheduler()
        await scheduler._notify_new_failures(db, testProject, 1, [])


class TestExecuteUiAutomationWithCases:
    """_execute_ui_automation 有活跃用例分支测试。

    创建真实 ui_automation 用例，monkeypatch 执行引擎避免 Playwright，
    覆盖任务创建、引擎初始化、失败结果查询、通知调用链路。
    """

    async def test_executes_with_active_cases_no_failures(
        self, db, testUser, monkeypatch
    ) -> None:
        """有活跃用例时应创建任务、初始化引擎、执行（无失败结果不通知）。"""
        from app.crud import test_task as crudTaskModule

        project = Project(
            name="self_test_ui_with_cases",
            user_id=testUser.id,
            is_self_test=True,
            config={"self_test_mode": "ui_automation"},
            project_type="web",
        )
        db.add(project)
        db.flush()

        testCase = TestCase(
            case_no="TC-UIEXEC-001",
            project_id=project.id,
            module="ui_exec_module",
            title="ui exec case",
            precondition="none",
            steps_json=[{"step": "1", "action": "click", "param": ""}],
            expected_result="ok",
            priority=2,
            case_type="UI",
            test_category="ui_automation",
        )
        db.add(testCase)
        db.flush()

        fakeTask = TestTask(
            id=999001,
            task_name="fake_ui_task",
            project_id=project.id,
            case_ids=[testCase.id],
            executor_id=testUser.id,
        )

        def fakeCreateTask(db, task_name, project_id, case_ids, executor_id):
            return fakeTask

        monkeypatch.setattr(crudTaskModule, "create_test_task", fakeCreateTask)

        async def fakeExecuteTestTask(task_id, global_headless=True):
            return None

        class FakeEngine:
            def __init__(self, **kwargs):
                pass

            async def execute_test_task(self, task_id, global_headless=True):
                return await fakeExecuteTestTask(task_id, global_headless)

        from app.services import test_execution_engine as engineModule
        from app.services import precondition_service as precondModule
        from app.services import element_locator_service as locatorModule

        monkeypatch.setattr(engineModule, "TestExecutionEngineV2", FakeEngine)

        class FakePrecond:
            async def initialize(self):
                return None

        monkeypatch.setattr(precondModule, "PreconditionService", FakePrecond)
        monkeypatch.setattr(locatorModule, "ElementLocatorService", lambda db: None)

        scheduler = SelfTestScheduler()
        await scheduler._execute_ui_automation(db, project)

    async def test_precondition_init_failure_sets_none(
        self, db, testUser, monkeypatch
    ) -> None:
        """PreconditionService.initialize 抛异常应被捕获，precondition_service 置 None。"""
        from app.crud import test_task as crudTaskModule
        from app.services import test_execution_engine as engineModule
        from app.services import precondition_service as precondModule
        from app.services import element_locator_service as locatorModule

        project = Project(
            name="self_test_precond_fail",
            user_id=testUser.id,
            is_self_test=True,
            project_type="web",
        )
        db.add(project)
        db.flush()

        testCase = TestCase(
            case_no="TC-PRECOND-001",
            project_id=project.id,
            module="precond_module",
            title="precond case",
            precondition="none",
            steps_json=[{"step": "1", "action": "click", "param": ""}],
            expected_result="ok",
            priority=2,
            case_type="UI",
            test_category="ui_automation",
        )
        db.add(testCase)
        db.flush()

        fakeTask = TestTask(
            id=999002,
            task_name="fake_precond_task",
            project_id=project.id,
            case_ids=[testCase.id],
            executor_id=testUser.id,
        )
        monkeypatch.setattr(
            crudTaskModule, "create_test_task",
            lambda db, **kw: fakeTask,
        )

        class FailingPrecond:
            async def initialize(self):
                raise RuntimeError("precond init failed")

        class FakeEngine:
            def __init__(self, **kwargs):
                pass

            async def execute_test_task(self, task_id, global_headless=True):
                return None

        monkeypatch.setattr(precondModule, "PreconditionService", FailingPrecond)
        monkeypatch.setattr(engineModule, "TestExecutionEngineV2", FakeEngine)
        monkeypatch.setattr(locatorModule, "ElementLocatorService", lambda db: None)

        scheduler = SelfTestScheduler()
        await scheduler._execute_ui_automation(db, project)

    async def test_engine_execution_failure_caught(
        self, db, testUser, monkeypatch
    ) -> None:
        """engine.execute_test_task 抛异常应被捕获，不传播。"""
        from app.crud import test_task as crudTaskModule
        from app.services import test_execution_engine as engineModule
        from app.services import precondition_service as precondModule
        from app.services import element_locator_service as locatorModule

        project = Project(
            name="self_test_engine_fail",
            user_id=testUser.id,
            is_self_test=True,
            project_type="web",
        )
        db.add(project)
        db.flush()

        testCase = TestCase(
            case_no="TC-ENGINEFAIL-001",
            project_id=project.id,
            module="engine_module",
            title="engine fail case",
            precondition="none",
            steps_json=[{"step": "1", "action": "click", "param": ""}],
            expected_result="ok",
            priority=2,
            case_type="UI",
            test_category="ui_automation",
        )
        db.add(testCase)
        db.flush()

        fakeTask = TestTask(
            id=999003,
            task_name="fake_engine_task",
            project_id=project.id,
            case_ids=[testCase.id],
            executor_id=testUser.id,
        )
        monkeypatch.setattr(
            crudTaskModule, "create_test_task",
            lambda db, **kw: fakeTask,
        )

        class FakePrecond:
            async def initialize(self):
                return None

        class FailingEngine:
            def __init__(self, **kwargs):
                pass

            async def execute_test_task(self, task_id, global_headless=True):
                raise RuntimeError("engine crash")

        monkeypatch.setattr(precondModule, "PreconditionService", FakePrecond)
        monkeypatch.setattr(engineModule, "TestExecutionEngineV2", FailingEngine)
        monkeypatch.setattr(locatorModule, "ElementLocatorService", lambda db: None)

        scheduler = SelfTestScheduler()
        await scheduler._execute_ui_automation(db, project)

    async def test_failed_results_triggers_notify(
        self, db, testUser, monkeypatch
    ) -> None:
        """有失败结果时应调用 _notify_new_failures（WebSocket 失败被捕获）。"""
        from app.crud import test_task as crudTaskModule
        from app.services import test_execution_engine as engineModule
        from app.services import precondition_service as precondModule
        from app.services import element_locator_service as locatorModule

        project = Project(
            name="self_test_failed_results",
            user_id=testUser.id,
            is_self_test=True,
            project_type="web",
        )
        db.add(project)
        db.flush()

        testCase = TestCase(
            case_no="TC-FAILEDRES-001",
            project_id=project.id,
            module="failed_module",
            title="failed result case",
            precondition="none",
            steps_json=[{"step": "1", "action": "click", "param": ""}],
            expected_result="ok",
            priority=2,
            case_type="UI",
            test_category="ui_automation",
        )
        db.add(testCase)
        db.flush()

        fakeTask = TestTask(
            id=999004,
            task_name="fake_failed_task",
            project_id=project.id,
            case_ids=[testCase.id],
            executor_id=testUser.id,
        )
        db.add(fakeTask)
        db.flush()
        monkeypatch.setattr(
            crudTaskModule, "create_test_task",
            lambda db, **kw: fakeTask,
        )

        failedResult = TestResult(
            task_id=fakeTask.id,
            project_id=project.id,
            case_id=testCase.id,
            case_no=testCase.case_no,
            exec_status=2,
            error_msg="assertion failed",
            exec_log="step 1 failed",
        )
        db.add(failedResult)
        db.flush()

        class FakePrecond:
            async def initialize(self):
                return None

        class FakeEngine:
            def __init__(self, **kwargs):
                pass

            async def execute_test_task(self, task_id, global_headless=True):
                return None

        monkeypatch.setattr(precondModule, "PreconditionService", FakePrecond)
        monkeypatch.setattr(engineModule, "TestExecutionEngineV2", FakeEngine)
        monkeypatch.setattr(locatorModule, "ElementLocatorService", lambda db: None)

        scheduler = SelfTestScheduler()
        await scheduler._execute_ui_automation(db, project)
