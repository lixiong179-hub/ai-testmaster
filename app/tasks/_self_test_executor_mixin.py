"""自测执行期辅助方法 Mixin。

从 `app/tasks/self_test_scheduler.py` 拆分而来，集中存放 SelfTestScheduler
执行期的 4 个辅助方法，避免单文件超过 350 行。

包含方法：
    - _execute_ui_automation: UI 自动化执行模式
    - _cleanup_self_test_data: 清理自测数据（解绑 Bug + 删除任务）
    - _notify_new_failures: WebSocket 推送失败用例通知
    - handle_step_failure: 步骤失败处理（自动创建 Bug + 通知）

兼容性：SelfTestScheduler 继承 SelfTestExecutorMixin，测试中
`scheduler._execute_ui_automation(...)` 等调用方式零改动。
"""
import asyncio
from typing import Dict, Iterable, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket import manager as ws_manager
from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.services.self_test_service import (
    _auto_create_defect_bug,
    _notify_critical_defect_bug,
)


class SelfTestExecutorMixin:
    """自测执行期辅助方法 Mixin，供 SelfTestScheduler 继承。

    这些方法均不依赖 SelfTestScheduler 的实例状态（_scheduler/_running_projects），
    仅作为逻辑分组放在独立模块，通过继承保持 `scheduler.xxx()` 调用兼容。
    """

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
        from app.models.test_task import TestTask

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
