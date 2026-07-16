"""
APScheduler 自测定时调度器测试模块

覆盖场景：
    - validate_cron_expression 合法/非法表达式
    - SelfTestScheduler.add_job cron 校验失败抛 ValueError
    - SelfTestScheduler.start/stop 正常流程
    - SelfTestScheduler.start 重复启动防护
    - SelfTestScheduler.add_job/remove_job 正常流程

使用真实 BackgroundScheduler + CronTrigger，不使用 Mock。
每个测试后调用 stop() 确保无残留调度器。
"""
import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models.project import Project
from app.tasks.self_test_scheduler import (
    SelfTestScheduler,
    validate_cron_expression,
)


class TestValidateCronExpression:
    """validate_cron_expression cron 表达式校验测试。"""

    @pytest.mark.parametrize(
        "expression",
        [
            "0 2 * * *",
            "*/30 * * * *",
            "* * * * *",
            "0 9-17 * * 1-5",
        ],
    )
    def test_valid_expression_returns_true(self, expression: str) -> None:
        """合法 cron 表达式应返回 True。"""
        assert validate_cron_expression(expression) is True

    @pytest.mark.parametrize(
        "expression",
        [
            "",
            "invalid",
            "99 99 99 99 99",
            "0 2 * *",
        ],
    )
    def test_invalid_expression_returns_false(self, expression: str) -> None:
        """非法 cron 表达式应返回 False（空串、垃圾字符、字段超范围、字段数不足）。"""
        assert validate_cron_expression(expression) is False


class TestSelfTestSchedulerLifecycle:
    """SelfTestScheduler 启停生命周期测试。"""

    def setup_method(self) -> None:
        self.scheduler = SelfTestScheduler()

    def teardown_method(self) -> None:
        self.scheduler.stop()

    def test_start_creates_running_scheduler(self) -> None:
        """start 后 _scheduler 不为 None 且处于运行状态。"""
        self.scheduler.start()
        assert self.scheduler._scheduler is not None
        assert isinstance(self.scheduler._scheduler, BackgroundScheduler)
        assert self.scheduler._scheduler.running is True

    def test_stop_clears_scheduler(self) -> None:
        """stop 后 _scheduler 应置 None。"""
        self.scheduler.start()
        self.scheduler.stop()
        assert self.scheduler._scheduler is None

    def test_start_idempotent_skips_duplicate(self) -> None:
        """重复启动应跳过，不创建新调度器（_scheduler.running 防护）。"""
        self.scheduler.start()
        first = self.scheduler._scheduler
        self.scheduler.start()
        assert self.scheduler._scheduler is first

    def test_stop_when_not_started_no_error(self) -> None:
        """未启动时 stop 不应抛异常（_scheduler 为 None 兜底）。"""
        self.scheduler.stop()
        assert self.scheduler._scheduler is None

    def test_remove_job_when_scheduler_none_no_error(self) -> None:
        """_scheduler 为 None 时 remove_job 应直接返回（边界兜底）。"""
        self.scheduler.remove_job(1)
        assert self.scheduler._scheduler is None


class TestSelfTestSchedulerAddRemoveJob:
    """SelfTestScheduler 任务添加/移除测试。"""

    def setup_method(self) -> None:
        self.scheduler = SelfTestScheduler()
        self.scheduler.start()

    def teardown_method(self) -> None:
        self.scheduler.stop()

    def test_add_job_registers_cron_job(self) -> None:
        """add_job 后任务应存在且使用 CronTrigger。"""
        self.scheduler.add_job(1, "0 2 * * *")
        jobId = SelfTestScheduler._make_job_id(1)
        job = self.scheduler._scheduler.get_job(jobId)
        assert job is not None
        assert job.id == jobId
        assert isinstance(job.trigger, CronTrigger)

    def test_add_job_invalid_cron_raises_value_error(self) -> None:
        """add_job 时 cron 校验失败应抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid cron expression"):
            self.scheduler.add_job(1, "invalid")

    def test_add_job_empty_cron_raises_value_error(self) -> None:
        """add_job 时空 cron 表达式应抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid cron expression"):
            self.scheduler.add_job(1, "")

    def test_add_job_out_of_range_cron_raises_value_error(self) -> None:
        """add_job 时字段超范围 cron 表达式应抛 ValueError。"""
        with pytest.raises(ValueError, match="invalid cron expression"):
            self.scheduler.add_job(1, "99 99 99 99 99")

    def test_add_job_replaces_existing(self) -> None:
        """add_job 同 project_id 应替换已有任务（replace_existing=True）。"""
        self.scheduler.add_job(1, "0 2 * * *")
        self.scheduler.add_job(1, "0 3 * * *")
        jobId = SelfTestScheduler._make_job_id(1)
        jobs = [
            j for j in self.scheduler._scheduler.get_jobs() if j.id == jobId
        ]
        assert len(jobs) == 1

    def test_remove_job_deletes_job(self) -> None:
        """remove_job 后任务应不存在。"""
        self.scheduler.add_job(1, "0 2 * * *")
        self.scheduler.remove_job(1)
        jobId = SelfTestScheduler._make_job_id(1)
        job = self.scheduler._scheduler.get_job(jobId)
        assert job is None

    def test_remove_nonexistent_job_no_error(self) -> None:
        """remove_job 不存在的任务不应抛异常（get_job 返回 None 兜底）。"""
        self.scheduler.remove_job(999)

    def test_make_job_id_format(self) -> None:
        """_make_job_id 应生成 self_test_{id} 格式。"""
        assert SelfTestScheduler._make_job_id(42) == "self_test_42"

    def test_add_job_without_start_auto_creates_scheduler(self) -> None:
        """add_job 在 _scheduler 为 None 时应自动创建调度器（实现内置兜底）。"""
        scheduler = SelfTestScheduler()
        try:
            scheduler.add_job(1, "0 2 * * *")
            assert scheduler._scheduler is not None
            jobId = SelfTestScheduler._make_job_id(1)
            job = scheduler._scheduler.get_job(jobId)
            assert job is not None
        finally:
            scheduler.stop()


class TestRefreshJobs:
    """refresh_jobs 调度任务刷新测试。

    使用真实数据库验证：自动启动调度器、按自测项目配置添加任务、
    清理无效任务、跳过无 schedule 的项目。
    """

    def setup_method(self) -> None:
        self.scheduler = SelfTestScheduler()

    def teardown_method(self) -> None:
        self.scheduler.stop()

    def test_refresh_starts_scheduler_when_none(self, db) -> None:
        """_scheduler 为 None 时 refresh_jobs 应自动启动调度器。"""
        assert self.scheduler._scheduler is None
        self.scheduler.refresh_jobs(db)
        assert self.scheduler._scheduler is not None
        assert self.scheduler._scheduler.running is True

    def test_refresh_adds_job_for_self_test_project_with_schedule(
        self, db, testUser
    ) -> None:
        """有 schedule 的自测项目应添加定时任务。"""
        from app.models.project import Project

        project = Project(
            name="self_test_refresh_add",
            user_id=testUser.id,
            is_self_test=True,
            self_test_schedule="0 2 * * *",
            project_type="web",
        )
        db.add(project)
        db.flush()
        try:
            self.scheduler.start()
            self.scheduler.refresh_jobs(db)
            jobId = SelfTestScheduler._make_job_id(project.id)
            assert self.scheduler._scheduler.get_job(jobId) is not None
        finally:
            self.scheduler.remove_job(project.id)

    def test_refresh_removes_orphan_jobs(self, db) -> None:
        """refresh_jobs 应清理不在有效列表中的 self_test_ 任务。"""
        self.scheduler.start()
        self.scheduler.add_job(99999, "0 2 * * *")
        orphanId = SelfTestScheduler._make_job_id(99999)
        assert self.scheduler._scheduler.get_job(orphanId) is not None
        self.scheduler.refresh_jobs(db)
        assert self.scheduler._scheduler.get_job(orphanId) is None

    def test_refresh_skips_project_without_schedule(self, db, testUser) -> None:
        """无 schedule 的自测项目应被跳过（不添加任务）。"""
        from app.models.project import Project

        project = Project(
            name="self_test_no_schedule",
            user_id=testUser.id,
            is_self_test=True,
            self_test_schedule=None,
            project_type="web",
        )
        db.add(project)
        db.flush()
        self.scheduler.start()
        self.scheduler.refresh_jobs(db)
        jobId = SelfTestScheduler._make_job_id(project.id)
        assert self.scheduler._scheduler.get_job(jobId) is None


class TestOnScheduleTriggered:
    """_on_schedule_triggered 调度触发测试。

    使用 monkeypatch 替换 _execute_self_test（涉及 Playwright 无法真实执行），
    验证并发防护、协程执行、异常捕获逻辑。
    """

    def setup_method(self) -> None:
        self.scheduler = SelfTestScheduler()

    def teardown_method(self) -> None:
        self.scheduler.stop()

    def test_already_running_project_skipped(self, monkeypatch) -> None:
        """project_id 已在 _running_projects 中应跳过执行。"""
        called = {"flag": False}

        def fakeExecute(pid: int) -> None:
            called["flag"] = True

        monkeypatch.setattr(self.scheduler, "_execute_self_test", fakeExecute)
        self.scheduler._running_projects.add(42)
        self.scheduler._on_schedule_triggered(42)
        assert called["flag"] is False
        assert 42 in self.scheduler._running_projects

    def test_sync_result_no_async_run(self, monkeypatch) -> None:
        """_execute_self_test 返回非协程时应跳过 asyncio.run。"""
        called = {"flag": False}

        def fakeExecute(pid: int) -> None:
            called["flag"] = True

        monkeypatch.setattr(self.scheduler, "_execute_self_test", fakeExecute)
        self.scheduler._on_schedule_triggered(42)
        assert called["flag"] is True
        assert 42 not in self.scheduler._running_projects

    def test_coroutine_result_runs_async(self, monkeypatch) -> None:
        """_execute_self_test 返回协程时应通过 asyncio.run 执行。"""
        called = {"flag": False}

        async def fakeExecute(pid: int) -> None:
            called["flag"] = True

        monkeypatch.setattr(self.scheduler, "_execute_self_test", fakeExecute)
        self.scheduler._on_schedule_triggered(42)
        assert called["flag"] is True
        assert 42 not in self.scheduler._running_projects

    def test_exception_caught_and_logged(self, monkeypatch) -> None:
        """_execute_self_test 抛异常应被捕获，不传播，finally 清理运行集合。"""

        def fakeExecute(pid: int) -> None:
            raise RuntimeError("boom")

        monkeypatch.setattr(self.scheduler, "_execute_self_test", fakeExecute)
        self.scheduler._on_schedule_triggered(42)
        assert 42 not in self.scheduler._running_projects


class TestGetSelfTestMode:
    """_get_self_test_mode 项目配置解析测试。

    覆盖 config 为 dict/JSON 字符串/None/非法值等多种场景，
    验证默认值兜底与模式合法性校验。
    """

    def test_dict_full_pipeline(self) -> None:
        """config 为 dict 且 self_test_mode=full_pipeline 应返回 full_pipeline。"""
        project = Project(config={"self_test_mode": "full_pipeline"})
        assert SelfTestScheduler._get_self_test_mode(project) == "full_pipeline"

    def test_dict_ui_automation(self) -> None:
        """config 为 dict 且 self_test_mode=ui_automation 应返回 ui_automation。"""
        project = Project(config={"self_test_mode": "ui_automation"})
        assert SelfTestScheduler._get_self_test_mode(project) == "ui_automation"

    def test_dict_no_mode_defaults(self) -> None:
        """config 为 dict 但无 self_test_mode 应默认 ui_automation。"""
        project = Project(config={})
        assert SelfTestScheduler._get_self_test_mode(project) == "ui_automation"

    def test_dict_invalid_mode_defaults(self) -> None:
        """config 为 dict 且 self_test_mode 非法应默认 ui_automation。"""
        project = Project(config={"self_test_mode": "unknown_mode"})
        assert SelfTestScheduler._get_self_test_mode(project) == "ui_automation"

    def test_json_string_full_pipeline(self) -> None:
        """config 为 JSON 字符串应解析并返回对应模式。"""
        project = Project(config='{"self_test_mode": "full_pipeline"}')
        assert SelfTestScheduler._get_self_test_mode(project) == "full_pipeline"

    def test_json_string_invalid_defaults(self) -> None:
        """config 为非法 JSON 字符串应默认 ui_automation。"""
        project = Project(config="not a json")
        assert SelfTestScheduler._get_self_test_mode(project) == "ui_automation"

    def test_none_config_defaults(self) -> None:
        """config 为 None 应默认 ui_automation。"""
        project = Project(config=None)
        assert SelfTestScheduler._get_self_test_mode(project) == "ui_automation"


class TestHandleStepFailure:
    """handle_step_failure 步骤失败处理测试。

    使用真实数据库与非自测项目，覆盖 _auto_create_defect_bug 返回 None
    时 handle_step_failure 直接返回 None 的分支，不触发 WebSocket 通知。
    """

    async def test_non_self_test_project_returns_none(
        self, db, testProject
    ) -> None:
        """非自测项目调用 handle_step_failure 应返回 None。

        _auto_create_defect_bug 校验 is_self_test 为 False 时直接返回 None，
        handle_step_failure 不创建 Bug、不通知、返回 None。
        """
        scheduler = SelfTestScheduler()
        result = await scheduler.handle_step_failure(
            db=db,
            project=testProject,
            failure_type="assertion",
            error_message="元素未找到",
            step_description="点击登录按钮",
        )
        assert result is None
