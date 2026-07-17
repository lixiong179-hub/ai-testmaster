"""Scheduled self-test execution support.

拆分说明：
    - 执行期辅助方法（_execute_ui_automation/_cleanup_self_test_data/
      _notify_new_failures/handle_step_failure）拆至
      `_self_test_executor_mixin.py`，避免单文件超 350 行；
    - SelfTestScheduler 继承 SelfTestExecutorMixin 保持
      `scheduler.xxx()` 调用方式零改动。
"""
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.services.self_test_service import run_defect_discovery_self_test
from app.tasks._self_test_executor_mixin import SelfTestExecutorMixin


def validate_cron_expression(expression: str) -> bool:
    if not expression:
        return False
    try:
        CronTrigger.from_crontab(expression)
        return True
    except Exception:
        return False


class SelfTestScheduler(SelfTestExecutorMixin):
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


__all__ = ["SelfTestScheduler", "validate_cron_expression"]
