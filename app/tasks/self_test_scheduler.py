"""Scheduled self-test execution support."""
import asyncio
from typing import Iterable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy.orm import Session

from app.core.websocket import manager as ws_manager
from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask


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

    def refresh_jobs(self, db: Session) -> None:
        if self._scheduler is None:
            self.start()
        valid_job_ids: set[str] = set()
        projects = db.query(Project).filter(Project.is_self_test.is_(True)).all()
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

        Args:
            project_id: 自测项目 ID。

        Raises:
            NotImplementedError: 自测执行逻辑尚未实现。
        """
        raise NotImplementedError(
            f"Self-test execution for project {project_id} is not yet implemented"
        )

    async def _cleanup_self_test_data(self, db: Session, task_id: int) -> None:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            return

        for bug in db.query(Bug).filter(Bug.test_result_id.in_(
            db.query(TestResult.id).filter(TestResult.task_id == task_id)
        )).all():
            result = bug.test_result
            if result:
                bug.reproduction_steps = (
                    f"错误信息: {result.error_msg or ''}\n"
                    f"执行日志: {result.exec_log or ''}"
                )
            bug.test_result_id = None

        db.delete(task)
        db.commit()

    async def _notify_new_failures(
        self,
        db: Session,
        project: Project,
        failed_count: int,
        failed_case_ids: Iterable[int],
    ) -> None:
        try:
            cases = db.query(TestCase).filter(TestCase.id.in_(list(failed_case_ids))).all()
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


__all__ = ["SelfTestScheduler", "validate_cron_expression"]
