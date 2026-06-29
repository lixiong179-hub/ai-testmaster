"""网址驱动快速测试 - 一键任务编排。

复用 `app/api/v1/endpoints/test_task.py` 的 `create_test_task` 与 `start_test_task`
核心逻辑（抽取为 TaskAssembler 的 assemble / create_skeleton_task 服务方法），
供 QuickLauncher 内部调用，禁 HTTP 自调用，零改动现有端点避免回归。

设计要点：
- assemble 支持 task_id=None（创建新任务，Task 7 spec 独立调用）与 task_id=已有
  （更新占位任务的 case_ids，QuickLauncher 预创建后实时推送编排阶段进度）双模式；
- execution_mode 固定 smart，复用 TestExecutionEngineV2 执行；
- 创建/更新失败回滚抛出；启动失败记录但不阻断，返回已创建任务供查询；
- 执行引擎在后台 asyncio.create_task 异步启动，assemble 立即返回，前端通过
  WebSocket 订阅 `task:{task_id}` 接收执行进度（执行引擎已有推送能力）。

边界场景：
- project 不存在 → 抛 ValueError；
- case_ids 为空 → 仍创建任务（total_count=0），执行引擎内部会置 PENDING 返回；
- 执行引擎抛异常 → 后台任务内捕获记录，任务状态由 executor 内部置 FAILED。
"""
import asyncio
from datetime import datetime
from typing import Callable, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.enums import ExecStatus
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TaskStatus, TestTask
from app.services.push_service import PushService, get_push_service
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.utils.db_time import utcnow

# 快速测试任务固定使用 smart 执行模式（spec Requirement: execution_mode = smart）
EXECUTION_MODE_SMART = "smart"
# 任务名时间戳格式：YYYYMMDDHHmmss，保证同项目多次快速测试任务名唯一可区分
_TASK_NAME_TS_FORMAT = "%Y%m%d%H%M%S"
# WebSocket 推送通道模板，与 QuickLauncher._CHANNEL_TEMPLATE 保持一致
_CHANNEL_TEMPLATE = "quick_test:{task_id}"


class TaskAssembler:
    """一键任务编排器，复用 test_task 端点逻辑供内部调用。

    依赖注入：
    - executor_factory: 接收 session 返回 TestExecutionEngineV2 的工厂，None 时用默认，
      支持测试注入 FakeExecutor 隔离真实执行。
    """

    def __init__(
        self,
        executor_factory: Optional[Callable[[Session], TestExecutionEngineV2]] = None,
        push_service: Optional[PushService] = None,
    ) -> None:
        """注入执行引擎工厂与推送服务。

        Args:
            executor_factory: 接收 session 返回 TestExecutionEngineV2 的工厂，
                None 时用默认 TestExecutionEngineV2(session)。
            push_service: WebSocket 推送服务，None 时用 get_push_service()。
                用于后台执行完成后向 quick_test:{task_id} 通道推送终态，
                确保前端 WebSocket 订阅方能收到完成/失败通知。
        """
        self._executor_factory = executor_factory or self._default_executor_factory
        self._push_service = push_service or get_push_service()

    @staticmethod
    def _default_executor_factory(session: Session) -> TestExecutionEngineV2:
        """默认执行引擎工厂，复用项目现有 TestExecutionEngineV2。"""
        return TestExecutionEngineV2(session)

    @staticmethod
    def derive_task_name(project: Project) -> str:
        """推导任务名：{项目名}_快速测试_{YYYYMMDDHHmmss}。

        时间戳精度到秒，保证同项目多次快速测试任务名唯一可区分。
        """
        ts = datetime.now().strftime(_TASK_NAME_TS_FORMAT)
        return f"{project.name}_快速测试_{ts}"

    def create_skeleton_task(
        self, project_id: int, user_id: int, session: Session
    ) -> TestTask:
        """预创建占位任务（case_ids 空），供 QuickLauncher 拿 task_id 用于 WebSocket 通道。

        不创建 TestResult，不启动执行；assemble 阶段会补齐 case_ids 与 TestResult 并启动。

        Args:
            project_id: 所属项目 ID。
            user_id: 执行人 ID（executor_id）。
            session: SQLAlchemy 会话，由调用方管理事务。

        Returns:
            TestTask: 已持久化的占位任务（status=PENDING, total_count=0）。

        Raises:
            ValueError: 项目不存在。
            Exception: DB 持久化失败时回滚抛出。
        """
        project = self._get_project(project_id, session)
        task_name = self.derive_task_name(project)
        task = TestTask(
            task_name=task_name,
            project_id=project_id,
            case_ids=[],
            executor_id=user_id,
            status=TaskStatus.PENDING,
            total_count=0,
            progress=0,
            success_count=0,
            fail_count=0,
        )
        session.add(task)
        try:
            session.commit()
            session.refresh(task)
        except Exception as exc:
            session.rollback()
            logger.error(f"占位任务创建失败: project_id={project_id} err={exc}")
            raise
        logger.info(f"占位任务创建成功: task_id={task.id} project_id={project_id}")
        return task

    async def assemble(
        self,
        project_id: int,
        case_ids: List[int],
        user_id: int,
        session: Session,
        task_id: Optional[int] = None,
    ) -> TestTask:
        """一键任务编排主方法：创建/更新任务 + 关联用例 + 启动执行。

        Args:
            project_id: 所属项目 ID。
            case_ids: 待执行用例 ID 列表（全部生成用例）。
            user_id: 执行人 ID（executor_id）。
            session: SQLAlchemy 会话，由调用方管理事务。
            task_id: 可选，已有任务 ID。None 时创建新任务（Task 7 spec 独立调用）；
                传入时更新该任务的 case_ids 与 total_count（QuickLauncher 预创建后补齐）。

        Returns:
            TestTask: 已创建/更新并启动执行的任务（含 task_id）。

        Raises:
            ValueError: 项目或任务不存在。
            Exception: 任务创建/更新失败时回滚抛出；启动失败不抛出（返回已创建任务）。
        """
        if task_id is None:
            task = self._create_task(project_id, case_ids, user_id, session)
        else:
            task = self._update_existing_task(task_id, case_ids, session)
        await self._start_task(task, session)
        return task

    def _create_task(
        self, project_id: int, case_ids: List[int], user_id: int, session: Session
    ) -> TestTask:
        """创建新 TestTask + TestResult（复刻 test_task.py 端点 create_test_task 逻辑）。"""
        project = self._get_project(project_id, session)
        task_name = self.derive_task_name(project)
        task = TestTask(
            task_name=task_name,
            project_id=project_id,
            case_ids=list(case_ids),
            executor_id=user_id,
            status=TaskStatus.PENDING,
            total_count=len(case_ids),
            progress=0,
            success_count=0,
            fail_count=0,
        )
        session.add(task)
        try:
            session.flush()
        except Exception as exc:
            session.rollback()
            logger.error(f"任务创建 flush 失败: project_id={project_id} err={exc}")
            raise
        self._build_test_results(task, case_ids, session)
        try:
            session.commit()
            session.refresh(task)
        except Exception as exc:
            session.rollback()
            logger.error(f"任务创建 commit 失败: task_id={task.id} err={exc}")
            raise
        logger.info(
            f"任务创建成功: task_id={task.id} project_id={project_id} "
            f"case_count={len(case_ids)}"
        )
        return task

    def _update_existing_task(
        self, task_id: int, case_ids: List[int], session: Session
    ) -> TestTask:
        """更新占位任务的 case_ids 与 total_count，补齐 TestResult。"""
        task = session.query(TestTask).filter(TestTask.id == task_id).first()
        if task is None:
            raise ValueError(f"待更新的任务不存在: task_id={task_id}")
        task.case_ids = list(case_ids)
        task.total_count = len(case_ids)
        try:
            session.flush()
        except Exception as exc:
            session.rollback()
            logger.error(f"任务更新 flush 失败: task_id={task_id} err={exc}")
            raise
        self._build_test_results(task, case_ids, session)
        try:
            session.commit()
            session.refresh(task)
        except Exception as exc:
            session.rollback()
            logger.error(f"任务更新 commit 失败: task_id={task_id} err={exc}")
            raise
        logger.info(f"任务更新成功: task_id={task_id} case_count={len(case_ids)}")
        return task

    def _build_test_results(
        self, task: TestTask, case_ids: List[int], session: Session
    ) -> None:
        """批量创建 TestResult（每条用例一条，NOT_EXECUTED），避免 N+1。

        复刻 test_task.py 端点：批量查询 TestCase 拿 case_no，bulk_insert_mappings
        批量插入，未匹配的 case_id 跳过（不阻断）。
        """
        if not case_ids:
            return
        cases = (
            session.query(TestCase)
            .filter(
                TestCase.id.in_(case_ids),
                TestCase.project_id == task.project_id,
                TestCase.is_deleted.is_(False),
            )
            .all()
        )
        case_map = {c.id: c for c in cases}
        mappings = []
        for case_id in case_ids:
            case = case_map.get(case_id)
            if case is None:
                logger.warning(f"用例不存在或已删除，跳过创建 TestResult: case_id={case_id}")
                continue
            mappings.append({
                "task_id": task.id,
                "project_id": task.project_id,
                "case_id": case_id,
                "case_no": case.case_no,
                "exec_status": int(ExecStatus.NOT_EXECUTED),
            })
        if mappings:
            session.bulk_insert_mappings(TestResult, mappings)

    async def _start_task(self, task: TestTask, session: Session) -> None:
        """启动任务执行：置 RUNNING + 异步触发执行引擎，异常不阻断。

        复刻 test_task.py 端点 start_test_task：置 status=RUNNING/start_time/commit，
        调用 TestExecutionEngineV2.execute_test_task。与端点不同：执行在后台
        asyncio.create_task 异步启动，assemble 立即返回，前端通过 WebSocket
        订阅 `task:{task_id}` 接收执行进度（执行引擎已有推送能力）。

        后台执行使用独立 session：request-scoped session 在请求结束后会被
        get_db() 关闭，后台任务若复用会因 session 已关闭导致后续 commit 静默失败
        （任务状态无法持久化为 COMPLETED/FAILED）。_run_executor_safely 内部
        通过 PrimarySessionLocal() 创建独立会话供执行引擎使用。
        """
        task.status = TaskStatus.RUNNING
        task.start_time = utcnow()
        try:
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error(f"任务启动状态更新失败: task_id={task.id} err={exc}")
            return
        asyncio.create_task(self._run_executor_safely(task.id))
        logger.info(f"任务已异步启动: task_id={task.id} execution_mode={EXECUTION_MODE_SMART}")

    async def _run_executor_safely(self, task_id: int) -> None:
        """后台执行任务（独立 session），捕获异常记录，避免 asyncio.create_task 吞异常。

        创建独立 PrimarySessionLocal 会话供执行引擎使用，避免复用 request-scoped
        session（已随请求结束被 get_db 关闭）。执行引擎内部已处理用例级异常
        并置 task 状态；此处仅兜底捕获引擎级异常（如 DB 连接断开），记录后
        尝试将任务置 FAILED，保证后台任务不污染事件循环。

        执行完成后向 quick_test:{task_id} 通道推送终态：launch API 同步推送
        编排阶段后即返回，实际执行在后台异步进行。前端 WebSocket 在 launch
        返回后才连接，onOpen 时 refreshStatus 只能拿到 RUNNING 态；若不补推
        终态，前端会永久卡在 running 视图，无法切换到 completed/failed。
        """
        from app.db.database import PrimarySessionLocal

        session = PrimarySessionLocal()
        try:
            executor = self._executor_factory(session)
            await executor.execute_test_task(
                task_id=task_id, execution_mode=EXECUTION_MODE_SMART
            )
        except Exception as exc:
            logger.error(f"任务执行引擎异常: task_id={task_id} err={exc}")
            try:
                task = session.query(TestTask).filter(TestTask.id == task_id).first()
                if task and task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.FAILED
                    task.end_time = utcnow()
                    session.commit()
            except Exception as inner:
                logger.error(f"任务失败状态持久化失败: task_id={task_id} err={inner}")
                session.rollback()
        finally:
            await self._push_final_status(task_id, session)
            session.close()

    async def _push_final_status(self, task_id: int, session: Session) -> None:
        """执行完成后推送终态到 quick_test:{task_id} 通道。

        查询任务最终状态，按 COMPLETED/FAILED/STOPPED 分别推送对应阶段，
        与前端 applyPushMessage 的终态分支及 _derive_stage 返回值对齐
        （stage=completed+done→completed，stage=failed→failed，
        stage=stopped→stopped）。STOPPED 是用户取消的终态，未来接入取消
        API 时前端能收到终态推送避免永久卡 running（spec BUG 10 预防性修复）。
        推送失败仅记录不阻断，不影响 session.close。
        """
        try:
            task = session.query(TestTask).filter(TestTask.id == task_id).first()
            if not task:
                return
            channel = _CHANNEL_TEMPLATE.format(task_id=task_id)
            if task.status == TaskStatus.COMPLETED:
                await self._push_service.push(channel, {
                    "stage": "completed", "status": "done", "progress": 100,
                    "detail": {"task_id": task_id},
                })
            elif task.status == TaskStatus.FAILED:
                await self._push_service.push(channel, {
                    "stage": "failed", "status": "error", "progress": 100,
                    "detail": {"message": "执行失败", "task_id": task_id},
                })
            elif task.status == TaskStatus.STOPPED:
                await self._push_service.push(channel, {
                    "stage": "stopped", "status": "done", "progress": 100,
                    "detail": {"message": "任务已停止", "task_id": task_id},
                })
        except Exception as exc:
            logger.warning(f"终态推送失败: task_id={task_id} err={exc}")

    def _get_project(self, project_id: int, session: Session) -> Project:
        """查询项目，不存在抛 ValueError（参数化查询防注入）。"""
        project = session.query(Project).filter(Project.id == project_id).first()
        if project is None:
            raise ValueError(f"项目不存在: project_id={project_id}")
        return project
