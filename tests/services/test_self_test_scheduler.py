"""
自测定时调度器单元测试

覆盖场景：
    - 添加/移除定时任务
    - cron表达式验证
    - 非自测项目不能配置定时计划
    - 自测执行后数据清理
    - WebSocket通知
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.websocket import manager as ws_manager
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.tasks.self_test_scheduler import (
    SelfTestScheduler,
    validate_cron_expression,
)


class TestValidateCronExpression:
    """cron表达式验证测试"""

    def test_valid_standard_cron(self) -> None:
        assert validate_cron_expression("0 2 * * *") is True

    def test_valid_every_minute(self) -> None:
        assert validate_cron_expression("* * * * *") is True

    def test_valid_with_step(self) -> None:
        assert validate_cron_expression("*/5 * * * *") is True

    def test_valid_with_range(self) -> None:
        assert validate_cron_expression("0 9-17 * * 1-5") is True

    def test_invalid_too_few_fields(self) -> None:
        assert validate_cron_expression("0 2 * *") is False

    def test_invalid_out_of_range(self) -> None:
        assert validate_cron_expression("60 2 * * *") is False

    def test_invalid_garbage(self) -> None:
        assert validate_cron_expression("abc") is False

    def test_empty_string(self) -> None:
        assert validate_cron_expression("") is False


class TestSelfTestSchedulerAddRemoveJob:
    """添加/移除定时任务测试"""

    def setup_method(self) -> None:
        self.scheduler = SelfTestScheduler()
        self.scheduler.start()

    def teardown_method(self) -> None:
        self.scheduler.stop()

    def test_add_job_success(self) -> None:
        self.scheduler.add_job(1, "0 2 * * *")
        job_id = SelfTestScheduler._make_job_id(1)
        job = self.scheduler._scheduler.get_job(job_id)
        assert job is not None
        assert job.id == job_id

    def test_add_job_replaces_existing(self) -> None:
        self.scheduler.add_job(1, "0 2 * * *")
        self.scheduler.add_job(1, "0 3 * * *")
        job_id = SelfTestScheduler._make_job_id(1)
        jobs = [
            j for j in self.scheduler._scheduler.get_jobs() if j.id == job_id
        ]
        assert len(jobs) == 1

    def test_remove_job_success(self) -> None:
        self.scheduler.add_job(1, "0 2 * * *")
        self.scheduler.remove_job(1)
        job_id = SelfTestScheduler._make_job_id(1)
        job = self.scheduler._scheduler.get_job(job_id)
        assert job is None

    def test_remove_nonexistent_job_no_error(self) -> None:
        self.scheduler.remove_job(999)

    def test_add_job_without_start_no_error(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler.add_job(1, "0 2 * * *")

    def test_make_job_id_format(self) -> None:
        assert SelfTestScheduler._make_job_id(42) == "self_test_42"


class TestSelfTestSchedulerRefreshJobs:
    """刷新定时任务测试"""

    def setup_method(self) -> None:
        self.scheduler = SelfTestScheduler()
        self.scheduler.start()

    def teardown_method(self) -> None:
        self.scheduler.stop()

    async def test_refresh_adds_scheduled_projects(
        self, async_db, async_test_user
    ) -> None:
        project = Project(
            name="scheduled_self_test",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
            self_test_schedule="0 2 * * *",
        )
        async_db.add(project)
        await async_db.flush()

        await self.scheduler.refresh_jobs(async_db)
        job_id = SelfTestScheduler._make_job_id(project.id)
        job = self.scheduler._scheduler.get_job(job_id)
        assert job is not None

    async def test_refresh_skips_projects_without_schedule(
        self, async_db, async_test_user
    ) -> None:
        project = Project(
            name="no_schedule_self_test",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
            self_test_schedule=None,
        )
        async_db.add(project)
        await async_db.flush()

        await self.scheduler.refresh_jobs(async_db)
        job_id = SelfTestScheduler._make_job_id(project.id)
        job = self.scheduler._scheduler.get_job(job_id)
        assert job is None

    async def test_refresh_skips_non_self_test_projects(
        self, async_db, async_test_user
    ) -> None:
        project = Project(
            name="normal_project_with_schedule",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=False,
            self_test_schedule="0 2 * * *",
        )
        async_db.add(project)
        await async_db.flush()

        await self.scheduler.refresh_jobs(async_db)
        job_id = SelfTestScheduler._make_job_id(project.id)
        job = self.scheduler._scheduler.get_job(job_id)
        assert job is None

    async def test_refresh_removes_stale_jobs(self, async_db) -> None:
        self.scheduler.add_job(99999, "0 2 * * *")
        await self.scheduler.refresh_jobs(async_db)
        job_id = SelfTestScheduler._make_job_id(99999)
        job = self.scheduler._scheduler.get_job(job_id)
        assert job is None


class TestSelfTestScheduleAPI:
    """自测定时计划API端点测试"""

    async def test_non_self_test_project_cannot_schedule(
        self, async_db, async_test_user
    ) -> None:
        from fastapi import HTTPException

        from app.api.v1.endpoints.project_core import update_self_test_schedule
        from app.api.v1.endpoints.project_core import SelfTestScheduleRequest

        project = Project(
            name="normal_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=False,
        )
        async_db.add(project)
        await async_db.flush()

        body = SelfTestScheduleRequest(schedule="0 2 * * *")
        with pytest.raises(HTTPException) as exc_info:
            await update_self_test_schedule(
                project_id=project.id,
                body=body,
                db=async_db,
                current_user=async_test_user,
            )
        assert exc_info.value.status_code == 400
        assert "仅自测项目" in exc_info.value.detail

    async def test_invalid_cron_expression_rejected(
        self, async_db, async_test_user
    ) -> None:
        from fastapi import HTTPException

        from app.api.v1.endpoints.project_core import update_self_test_schedule
        from app.api.v1.endpoints.project_core import SelfTestScheduleRequest

        project = Project(
            name="self_test_invalid_cron",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        body = SelfTestScheduleRequest(schedule="invalid cron")
        with pytest.raises(HTTPException) as exc_info:
            await update_self_test_schedule(
                project_id=project.id,
                body=body,
                db=async_db,
                current_user=async_test_user,
            )
        assert exc_info.value.status_code == 400
        assert "无效的cron表达式" in exc_info.value.detail

    async def test_null_schedule_cancels_timer(
        self, async_db, async_test_user
    ) -> None:
        from app.api.v1.endpoints.project_core import update_self_test_schedule
        from app.api.v1.endpoints.project_core import SelfTestScheduleRequest

        project = Project(
            name="self_test_cancel_schedule",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
            self_test_schedule="0 2 * * *",
        )
        async_db.add(project)
        await async_db.flush()

        body = SelfTestScheduleRequest(schedule=None)
        result = await update_self_test_schedule(
            project_id=project.id,
            body=body,
            db=async_db,
            current_user=async_test_user,
        )
        assert result["data"]["self_test_schedule"] is None

    async def test_nonexistent_project_returns_404(self, async_db, async_test_user) -> None:
        from fastapi import HTTPException

        from app.api.v1.endpoints.project_core import update_self_test_schedule
        from app.api.v1.endpoints.project_core import SelfTestScheduleRequest

        body = SelfTestScheduleRequest(schedule="0 2 * * *")
        with pytest.raises(HTTPException) as exc_info:
            await update_self_test_schedule(
                project_id=999999,
                body=body,
                db=async_db,
                current_user=async_test_user,
            )
        assert exc_info.value.status_code == 404


class TestSelfTestDataCleanup:
    """自测执行后数据清理测试"""

    async def _create_test_case(self, async_db, project_id: int) -> TestCase:
        """辅助方法：创建测试用例"""
        test_case = TestCase(
            title="自测用例",
            case_no="TC-CLEANUP-001",
            project_id=project_id,
            module="自测模块",
            precondition="无",
            steps_json=[],
            expected_result="执行成功",
            priority=2,
            case_type="UI",
        )
        async_db.add(test_case)
        await async_db.flush()
        return test_case

    async def test_cleanup_removes_task_but_preserves_results(
        self, async_db, async_test_user
    ) -> None:
        project = Project(
            name="cleanup_test_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        test_case = await self._create_test_case(async_db, project.id)

        task = TestTask(
            task_name="自测定时执行 - cleanup_test_project",
            project_id=project.id,
            case_ids=[test_case.id],
            executor_id=async_test_user.id,
            status=2,
            total_count=1,
        )
        async_db.add(task)
        await async_db.flush()

        result = TestResult(
            task_id=task.id,
            project_id=project.id,
            case_id=test_case.id,
            case_no=test_case.case_no,
            exec_status=2,
        )
        async_db.add(result)
        await async_db.flush()

        scheduler = SelfTestScheduler()
        await scheduler._cleanup_self_test_data(async_db, task.id)

        taskResult = (
            await async_db.execute(
                select(TestTask).where(TestTask.id == task.id)
            )
        ).scalars().first()
        assert taskResult is None
        resultResult = (
            await async_db.execute(
                select(TestResult).where(TestResult.id == result.id)
            )
        ).scalars().first()
        assert resultResult is not None

    async def test_cleanup_nonexistent_task_no_error(self, async_db) -> None:
        scheduler = SelfTestScheduler()
        await scheduler._cleanup_self_test_data(async_db, 999999)

    async def test_cleanup_preserves_self_test_bugs(
        self, async_db, async_test_user
    ) -> None:
        from app.models.bug import Bug

        project = Project(
            name="cleanup_bug_test_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        test_case = await self._create_test_case(async_db, project.id)

        task = TestTask(
            task_name="自测定时执行 - cleanup_bug_test_project",
            project_id=project.id,
            case_ids=[test_case.id],
            executor_id=async_test_user.id,
            status=2,
            total_count=1,
        )
        async_db.add(task)
        await async_db.flush()

        result = TestResult(
            task_id=task.id,
            project_id=project.id,
            case_id=test_case.id,
            case_no=test_case.case_no,
            exec_status=2,
            error_msg="元素点击失败",
            exec_log="步骤1: 打开页面\n步骤2: 点击按钮",
        )
        async_db.add(result)
        await async_db.flush()

        bug = Bug(
            bug_no=f"BUG-{project.id}-2026-0001",
            project_id=project.id,
            title="自测发现缺陷",
            description="测试描述",
            severity=3,
            priority=2,
            status="open",
            source="self_test",
            reporter_id=async_test_user.id,
            test_result_id=result.id,
        )
        async_db.add(bug)
        await async_db.flush()

        scheduler = SelfTestScheduler()
        await scheduler._cleanup_self_test_data(async_db, task.id)

        preserved_bug = (
            await async_db.execute(
                select(Bug).where(Bug.id == bug.id)
            )
        ).scalars().first()
        assert preserved_bug is not None
        assert preserved_bug.source == "self_test"
        assert preserved_bug.test_result_id is None
        assert "错误信息" in preserved_bug.reproduction_steps
        assert "执行日志" in preserved_bug.reproduction_steps
        resultResult = (
            await async_db.execute(
                select(TestResult).where(TestResult.id == result.id)
            )
        ).scalars().first()
        assert resultResult is not None
        taskResult = (
            await async_db.execute(
                select(TestTask).where(TestTask.id == task.id)
            )
        ).scalars().first()
        assert taskResult is None


class TestSelfTestWebSocketNotification:
    """WebSocket通知测试"""

    async def test_notify_new_failures_broadcasts_message(
        self, async_db, async_test_user
    ) -> None:
        project = Project(
            name="ws_notify_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        test_case = TestCase(
            title="失败用例",
            case_no="TC-WS-001",
            project_id=project.id,
            module="通知模块",
            precondition="无",
            steps_json=[],
            expected_result="执行成功",
            priority=2,
            case_type="UI",
        )
        async_db.add(test_case)
        await async_db.flush()

        scheduler = SelfTestScheduler()

        with patch.object(
            ws_manager, "broadcast", new_callable=AsyncMock
        ) as mock_broadcast:
            await scheduler._notify_new_failures(
                async_db, project, 1, {test_case.id}
            )
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args
            message = call_args[0][1]
            assert message["type"] == "self_test_notification"
            assert message["project_id"] == project.id
            assert message["project_name"] == project.name
            assert message["failed_count"] == 1
            assert len(message["new_failed_cases"]) == 1
            assert message["new_failed_cases"][0]["case_id"] == test_case.id

    async def test_notify_failure_broadcast_error_handled(
        self, async_db, async_test_user
    ) -> None:
        project = Project(
            name="ws_error_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        scheduler = SelfTestScheduler()

        with patch.object(
            ws_manager, "broadcast", new_callable=AsyncMock, side_effect=Exception("WS error")
        ):
            await scheduler._notify_new_failures(async_db, project, 1, set())


class TestSelfTestSchedulerStartStop:
    """调度器启停测试"""

    def test_start_creates_scheduler(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler.start()
        assert scheduler._scheduler is not None
        assert scheduler._scheduler.running is True
        scheduler.stop()

    def test_stop_clears_scheduler(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler.start()
        scheduler.stop()
        assert scheduler._scheduler is None

    def test_double_start_no_error(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler.start()
        scheduler.start()
        scheduler.stop()

    def test_double_stop_no_error(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler.stop()


class TestSelfTestSchedulerConcurrencyControl:
    """定时调度器并发控制测试"""

    def test_running_projects_initialized_empty(self) -> None:
        scheduler = SelfTestScheduler()
        assert len(scheduler._running_projects) == 0

    def test_concurrent_trigger_skips_running_project(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler._running_projects.add(42)

        with patch.object(
            scheduler, "_execute_self_test", new_callable=AsyncMock
        ):
            scheduler._on_schedule_triggered(42)
            assert 42 in scheduler._running_projects

    def test_project_removed_from_running_after_execution(self) -> None:
        scheduler = SelfTestScheduler()

        with patch.object(
            scheduler, "_execute_self_test", new_callable=AsyncMock
        ):
            scheduler._on_schedule_triggered(42)

        assert 42 not in scheduler._running_projects

    def test_project_removed_from_running_on_exception(self) -> None:
        scheduler = SelfTestScheduler()

        with patch.object(
            scheduler, "_execute_self_test", new_callable=AsyncMock, side_effect=Exception("boom")
        ):
            scheduler._on_schedule_triggered(42)

        assert 42 not in scheduler._running_projects

    def test_different_projects_run_concurrently(self) -> None:
        scheduler = SelfTestScheduler()
        scheduler._running_projects.add(1)

        with patch.object(
            scheduler, "_execute_self_test", new_callable=AsyncMock
        ):
            scheduler._on_schedule_triggered(2)

        assert 1 in scheduler._running_projects
        assert 2 not in scheduler._running_projects
