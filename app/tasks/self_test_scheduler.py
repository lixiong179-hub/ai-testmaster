"""Scheduled self-test execution support."""
import asyncio
from typing import Any, Dict, Iterable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import manager as ws_manager
from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.services.self_test_service import (
    _auto_create_defect_bug,
    _notify_critical_defect_bug,
    run_defect_discovery_self_test,
)


def validate_cron_expression(expression: str) -> bool:
    if not expression:
        return False
    try:
        CronTrigger.from_crontab(expression)
        return True
    except Exception:
        return False


class SelfTestScheduler:
    def __init__(self) -> None:
        self._scheduler: BackgroundScheduler | None = None
        self._running_projects: set[int] = set()

    @staticmethod
    def _make_job_id(project_id: int) -> str:
        return f"self_test_{project_id}"

    def start(self) -> None:
        if self._scheduler and self._scheduler.running:
            return
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler:
            if self._scheduler.running:
                self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def add_job(self, project_id: int, schedule: str) -> None:
        if not validate_cron_expression(schedule):
            raise ValueError("invalid cron expression")
        if self._scheduler is None:
            self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(
            func=self._on_schedule_triggered,
            trigger=CronTrigger.from_crontab(schedule),
            args=[project_id],
            id=self._make_job_id(project_id),
            replace_existing=True,
        )

    def remove_job(self, project_id: int) -> None:
        if not self._scheduler:
            return
        job_id = self._make_job_id(project_id)
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    async def refresh_jobs(self, db: AsyncSession) -> None:
        """从数据库刷新所有自测项目的调度任务。

        Args:
            db: 异步数据库会话。
        """
        if self._scheduler is None:
            self.start()
        valid_job_ids: set[str] = set()
        projects = (
            await db.execute(
                select(Project).where(Project.is_self_test.is_(True))
            )
        ).scalars().all()
        for project in projects:
            if project.self_test_schedule:
                self.add_job(project.id, project.self_test_schedule)
                valid_job_ids.add(self._make_job_id(project.id))

        for job in list(self._scheduler.get_jobs()):
            if job.id.startswith("self_test_") and job.id not in valid_job_ids:
                self._scheduler.remove_job(job.id)

    def _on_schedule_triggered(self, project_id: int) -> None:
        if project_id in self._running_projects:
            logger.warning("Self-test project %s is already running", project_id)
            return
        self._running_projects.add(project_id)
        try:
            result = self._execute_self_test(project_id)
            if asyncio.iscoroutine(result):
                asyncio.run(result)
        except Exception as exc:
            logger.error("Self-test execution failed: %s", exc)
        finally:
            self._running_projects.discard(project_id)

    async def _execute_self_test(self, project_id: int) -> None:
        """执行自测项目的测试任务。

        根据项目配置中的 self_test_mode 选择执行模式:
        - full_pipeline: 缺陷挖掘导向全链路执行（需求确认->测试点->用例->评审->任务->执行->评估->报告->清理）
        - ui_automation: 仅 UI 自动化执行（保持原有逻辑）

        Args:
            project_id: 自测项目 ID。
        """
        from app.db.database import AsyncPrimarySessionLocal

        db = AsyncPrimarySessionLocal()
        try:
            project = (
                await db.execute(
                    select(Project).where(Project.id == project_id)
                )
            ).scalars().first()
            if not project:
                logger.error(f"自测项目不存在: {project_id}")
                return

            # 读取项目配置中的 self_test_mode
            self_test_mode = self._get_self_test_mode(project)

            if self_test_mode == "full_pipeline":
                logger.info(
                    f"自测项目 {project_id} 使用全链路执行模式 (full_pipeline)"
                )
                result = await run_defect_discovery_self_test(
                    db=db,
                    project_id=project_id,
                    user_id=project.user_id,
                )
                logger.info(
                    f"自测项目 {project_id} 全链路执行完成: "
                    f"success={result.get('success')}, "
                    f"defects={result.get('defect_summary')}"
                )
            else:
                logger.info(
                    f"自测项目 {project_id} 使用 UI 自动化执行模式 (ui_automation)"
                )
                # ui_automation 模式保持原有逻辑：仅执行已有用例
                await self._execute_ui_automation(db, project)

        except Exception as exc:
            logger.error(f"自测执行失败: project_id={project_id}, error={exc}")
        finally:
            await db.close()

    @staticmethod
    def _get_self_test_mode(project: Project) -> str:
        """从项目配置中获取 self_test_mode。

        优先从 project.config JSON 字段读取 self_test_mode，
        未配置时默认为 ui_automation。

        Args:
            project: 项目实例。

        Returns:
            执行模式字符串: "full_pipeline" 或 "ui_automation"。
        """
        config = project.config
        if isinstance(config, str):
            try:
                import json
                config = json.loads(config)
            except (TypeError, ValueError):
                config = {}
        if isinstance(config, dict):
            mode = config.get("self_test_mode", "ui_automation")
            if mode in ("full_pipeline", "ui_automation"):
                return mode
        return "ui_automation"

    async def _execute_ui_automation(
        self,
        db: AsyncSession,
        project: Project,
    ) -> None:
        """UI 自动化执行模式：仅执行项目下已有的活跃用例。

        创建任务、启动执行引擎、处理失败结果。
        执行引擎内部使用 sync Session，通过 run_async_coro_in_thread
        在独立线程中运行避免阻塞事件循环。

        Args:
            db: 异步数据库会话。
            project: 自测项目实例。
        """
        from app.crud.test_task import create_test_task_async
        from app.models.enums import ExecStatus

        # 查询项目下所有活跃用例
        active_cases = (
            await db.execute(
                select(TestCase).where(
                    TestCase.project_id == project.id,
                    TestCase.is_deleted.is_(False),
                    TestCase.test_category == "ui_automation",
                )
            )
        ).scalars().all()
        if not active_cases:
            logger.warning(
                f"自测项目 {project.id} 无活跃 UI 自动化用例，跳过执行"
            )
            return

        case_ids = [tc.id for tc in active_cases]
        task = await create_test_task_async(
            db=db,
            task_name=f"UI自动化自测-{asyncio.get_event_loop().time():.0f}",
            project_id=project.id,
            case_ids=case_ids,
            executor_id=project.user_id,
        )

        # 启动执行引擎 - TestExecutionEngineV2 内部使用 sync Session
        from app.db.database import PrimarySessionLocal
        from app.services.test_execution_engine import TestExecutionEngineV2
        from app.services.precondition_service import PreconditionService
        from app.services.element_locator_service import ElementLocatorService
        from app.utils.async_sync_bridge import run_async_coro_in_thread

        try:
            precondition_service = PreconditionService()
            await precondition_service.initialize()
        except Exception as exc:
            logger.warning(f"前置条件服务初始化失败: {exc}")
            precondition_service = None

        sync_db = PrimarySessionLocal()
        try:
            locator_service = ElementLocatorService(sync_db)
            engine = TestExecutionEngineV2(
                db=sync_db,
                precondition_service=precondition_service,
                locator_service=locator_service,
            )

            try:
                await run_async_coro_in_thread(
                    engine.execute_test_task(task_id=task.id, global_headless=True)
                )
            except Exception as exc:
                logger.error(f"UI 自动化执行失败: {exc}")
        finally:
            sync_db.close()

        # 处理失败结果
        failed_results = (
            await db.execute(
                select(TestResult).where(
                    TestResult.project_id == project.id,
                    TestResult.task_id == task.id,
                    TestResult.exec_status.in_([ExecStatus.FAILED, ExecStatus.BLOCKED]),
                )
            )
        ).scalars().all()

        if failed_results:
            failed_case_ids = [r.case_id for r in failed_results]
            await self._notify_new_failures(
                db, project, len(failed_results), failed_case_ids
            )

    async def _cleanup_self_test_data(self, db: AsyncSession, task_id: int) -> None:
        """清理指定任务的自测数据：解绑 Bug 关联并删除任务。

        Args:
            db: 异步数据库会话。
            task_id: 测试任务 ID。
        """
        task = (
            await db.execute(
                select(TestTask).where(TestTask.id == task_id)
            )
        ).scalars().first()
        if not task:
            return

        # 子查询：task_id 关联的 TestResult.id
        from sqlalchemy.orm import selectinload

        result_id_subquery = select(TestResult.id).where(
            TestResult.task_id == task_id
        )
        bugs = (
            await db.execute(
                select(Bug)
                .options(selectinload(Bug.test_result))
                .where(Bug.test_result_id.in_(result_id_subquery))
            )
        ).scalars().all()
        for bug in bugs:
            result = bug.test_result
            if result:
                bug.reproduction_steps = (
                    f"错误信息: {result.error_msg or ''}\n"
                    f"执行日志: {result.exec_log or ''}"
                )
            bug.test_result_id = None

        await db.delete(task)
        await db.commit()

    async def _notify_new_failures(
        self,
        db: AsyncSession,
        project: Project,
        failed_count: int,
        failed_case_ids: Iterable[int],
    ) -> None:
        """通过 WebSocket 推送新失败用例通知。

        Args:
            db: 异步数据库会话。
            project: 自测项目实例。
            failed_count: 失败用例数。
            failed_case_ids: 失败用例 ID 列表。
        """
        try:
            cases = (
                await db.execute(
                    select(TestCase).where(
                        TestCase.id.in_(list(failed_case_ids))
                    )
                )
            ).scalars().all()
            message = {
                "type": "self_test_notification",
                "project_id": project.id,
                "project_name": project.name,
                "failed_count": failed_count,
                "new_failed_cases": [
                    {"case_id": case.id, "case_title": case.title, "case_no": case.case_no}
                    for case in cases
                ],
            }
            await ws_manager.broadcast(str(project.id), message)
        except Exception as exc:
            logger.warning("Self-test WebSocket notification failed: %s", exc)

    async def handle_step_failure(
        self,
        db: AsyncSession,
        project: Project,
        failure_type: str,
        error_message: str,
        defect_evidence: Optional[Dict] = None,
        test_case_id: Optional[int] = None,
        test_result_id: Optional[int] = None,
        step_description: str = "",
    ) -> Optional[Bug]:
        """处理步骤失败：自动创建 Bug 并按严重度决定是否立即通知。

        P0/P1 缺陷自动创建 Bug 后立即通过 WebSocket 推送通知；
        P2/P3 缺陷仅创建 Bug 记录，不立即通知，等待定期汇总。

        Args:
            db: 异步数据库会话。
            project: 关联的项目实例。
            failure_type: 断言类型或缺陷来源标识。
            error_message: 步骤执行错误信息。
            defect_evidence: 浏览器缺陷证据字典。
            test_case_id: 关联测试用例 ID。
            test_result_id: 关联执行结果 ID。
            step_description: 步骤描述。

        Returns:
            创建的 Bug 实例，未创建时返回 None。
        """
        bug = await _auto_create_defect_bug(
            db=db,
            project=project,
            failure_type=failure_type,
            error_message=error_message,
            defect_evidence=defect_evidence,
            test_case_id=test_case_id,
            test_result_id=test_result_id,
            step_description=step_description,
        )
        if bug is None:
            return None

        # P0/P1 缺陷立即通知管理员
        if bug.severity <= 2:
            await _notify_critical_defect_bug(bug, project)

        return bug


__all__ = ["SelfTestScheduler", "validate_cron_expression"]
