"""任务超时监控服务（P1 E-08：超时任务自动停止）

业务背景：
    测试任务在执行引擎中通过独立线程运行（run_async_coro_in_thread），
    当任务因异常/外部因素僵死时，会长期停留在 RUNNING 状态，持续占用
    执行线程、DB 连接与浏览器进程。本服务作为后台协程周期性扫描
    RUNNING 任务，将超过阈值的任务自动标记为 FAILED 并记录原因，
    避免僵死任务累积拖垮系统。

设计要点：
    - 单例 timeout_monitor，在 FastAPI lifespan 中启动/停止
    - 使用 AsyncPrimarySessionLocal 独立会话，与请求会话隔离
    - 时间基准统一 UTC（start_time 由 utcnow() 写入，阈值也用 utcnow() 计算，
      避免 naive/local 混用导致 8 小时偏差）
    - 两步法避免循环内 SQL（杜绝 N+1）：
        1) 单次 SELECT 收集超时候选任务 ID
        2) 单次 bulk UPDATE 标记失败（附加 status=RUNNING 条件防并发覆盖
           引擎刚刚写入的终态）
        3) 单次 SELECT 确认实际被更新的任务 ID（UPDATE 与 SELECT 之间
           引擎可能完成部分任务，仅对真正被标记为超时的任务发通知）
    - WebSocket 通知通过 PushService 统一抽象（通道 task:{task_id}），
      推送失败仅记录 warning，不影响主流程
    - 依赖注入：session_factory / push_service 可替换，便于单元测试

依赖关系：
    - app.core.config.settings              : 超时阈值与轮询间隔
    - app.db.database.AsyncPrimarySessionLocal : 异步会话工厂
    - app.utils.db_time.utcnow              : UTC 时间基准
    - app.services.push_service.PushService : WebSocket 推送
    - app.services.execution_control_manager.execution_controller : 清理执行控制器
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncPrimarySessionLocal
from app.models.test_task import TestTask, TaskStatus
from app.services.execution_control_manager import execution_controller
from app.utils.db_time import utcnow


class TaskTimeoutMonitor:
    """任务超时监控器（单例）。

    职责：
        - 启动/停止后台监控协程
        - 周期性扫描 RUNNING 超时任务并标记为 FAILED
        - 通过 WebSocket 通知前端任务已超时停止

    使用场景：
        - FastAPI lifespan startup 启动监控
        - lifespan shutdown 停止监控，避免事件循环关闭后协程残留

    设计意图：
        将超时检测从执行引擎中解耦，引擎无需感知时间阈值；
        监控器作为旁路组件，对僵死任务做兜底回收。
    """

    def __init__(
        self,
        session_factory=None,
        push_service=None,
    ) -> None:
        """初始化监控器。

        Args:
            session_factory: 异步会话工厂，默认 AsyncPrimarySessionLocal。
                测试时可注入事务隔离会话工厂以保持数据可见性。
            push_service: WebSocket 推送服务实例，可选（延迟加载）。
                测试时可注入 Mock 以断言推送行为。
        """
        self._session_factory = session_factory or AsyncPrimarySessionLocal
        self._push_service = push_service
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False

    async def start(self) -> None:
        """启动超时监控后台协程。

        边界场景：
            - 已运行时重复调用直接返回（幂等）
            - TIMEOUT_CHECK_INTERVAL<=0 视为关闭监控，仅记录日志
        """
        if self._running:
            logger.info("任务超时监控已在运行，跳过重复启动")
            return
        # 间隔非正数：灰度关闭监控，不启动循环
        if settings.TIMEOUT_CHECK_INTERVAL <= 0:
            logger.warning(
                f"TIMEOUT_CHECK_INTERVAL={settings.TIMEOUT_CHECK_INTERVAL}，"
                f"任务超时监控未启动（已通过配置关闭）"
            )
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"任务超时监控已启动：检测间隔 {settings.TIMEOUT_CHECK_INTERVAL}s，"
            f"超时阈值 {settings.TASK_TIMEOUT_SECONDS}s"
        )

    async def stop(self) -> None:
        """停止超时监控，取消后台协程并等待清理完成。

        边界场景：未启动时调用安全（self._task 为 None）。
        """
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"停止任务超时监控时捕获异常: {e}")
            self._task = None
        logger.info("任务超时监控已停止")

    @property
    def is_running(self) -> bool:
        """监控协程是否在运行。"""
        return self._running

    async def _monitor_loop(self) -> None:
        """监控主循环：周期性 sleep + 检测。

        异常处理：单次检测异常不中断循环，仅记录日志，避免瞬时
        DB 抖动导致监控永久失效。
        """
        while self._running:
            try:
                await asyncio.sleep(settings.TIMEOUT_CHECK_INTERVAL)
                await self._run_once()
            except asyncio.CancelledError:
                # 停止信号：优雅退出循环
                break
            except Exception as e:
                # 单次检测异常不影响后续轮询
                logger.exception(f"任务超时监控轮询异常: {e}")

    async def _run_once(self) -> None:
        """单次检测：创建独立会话执行检测逻辑。

        会话与请求会话隔离，提交后归还连接池。异常自动回滚。
        """
        async with self._session_factory() as db:
            try:
                await self._check_timeout_tasks(db)
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    async def _check_timeout_tasks(self, db: AsyncSession) -> None:
        """检测并处理超时任务（核心逻辑，可独立单测）。

        两步法避免循环内 SQL：
            1. SELECT 收集超时候选 ID（status=RUNNING 且 start_time 超过阈值）
            2. bulk UPDATE 标记失败（附加 status=RUNNING 条件防并发覆盖）
            3. SELECT 确认实际被标记为超时的任务 ID
            4. 对确认的任务发 WebSocket 通知 + 注销执行控制器（无 SQL）

        Args:
            db: 异步会话。生产由 _run_once 传入独立会话；
                测试可传入事务隔离 fixture 会话。
        """
        threshold_time = utcnow() - timedelta(seconds=settings.TASK_TIMEOUT_SECONDS)

        # Step 1：收集超时候选任务 ID（start_time 为 NULL 的未启动任务不参与判定）
        candidate_result = await db.execute(
            select(TestTask.id).where(
                TestTask.status == TaskStatus.RUNNING,
                TestTask.start_time.isnot(None),
                TestTask.start_time < threshold_time,
            )
        )
        candidate_ids: List[int] = [row[0] for row in candidate_result.all()]
        if not candidate_ids:
            return

        timeout_reason = f"任务执行超时（超过 {settings.TASK_TIMEOUT_SECONDS} 秒）"

        # Step 2：批量标记失败（WHERE 附 status=RUNNING 条件，防覆盖引擎刚写入的终态）
        await db.execute(
            update(TestTask)
            .where(
                TestTask.id.in_(candidate_ids),
                TestTask.status == TaskStatus.RUNNING,
            )
            .values(
                status=TaskStatus.FAILED,
                end_time=utcnow(),
                error_message=timeout_reason,
            )
        )

        # Step 3：确认实际被标记为超时的任务（status=FAILED 且 error_message 命中超时原因）
        confirmed_result = await db.execute(
            select(TestTask.id).where(
                TestTask.id.in_(candidate_ids),
                TestTask.status == TaskStatus.FAILED,
                TestTask.error_message == timeout_reason,
            )
        )
        confirmed_ids: List[int] = [row[0] for row in confirmed_result.all()]
        if not confirmed_ids:
            return

        logger.warning(
            f"检测到 {len(confirmed_ids)} 个超时任务，已自动标记为 FAILED：ids={confirmed_ids}"
        )

        # Step 4：通知前端 + 清理执行控制器（循环内无 SQL，仅内存态与 WebSocket IO）
        await self._notify_timeout(confirmed_ids, timeout_reason)

    async def _notify_timeout(self, task_ids: List[int], reason: str) -> None:
        """对超时任务发送 WebSocket 通知并注销执行控制器。

        容错设计：单个任务通知/注销失败不影响其他任务，仅记录 warning。

        Args:
            task_ids: 实际被标记为超时的任务 ID 列表。
            reason: 超时原因文本（用于前端展示）。
        """
        push_service = self._get_push_service()
        for task_id in task_ids:
            # 注销执行控制器：清理暂停/恢复控制句柄（幂等，不存在时安全）
            try:
                execution_controller.unregister(task_id)
            except Exception as e:
                logger.warning(f"注销执行控制器失败 task_id={task_id}: {e}")

            # WebSocket 通知前端：通道 task:{task_id}（PushService 内部转 execution_id）
            try:
                await push_service.push(
                    f"task:{task_id}",
                    {
                        "type": "task_timeout",
                        "task_id": task_id,
                        "status": "failed",
                        "message": "任务执行超时，已自动停止",
                        "reason": reason,
                    },
                )
            except Exception as e:
                # 推送失败不影响已落库的 FAILED 状态，仅记录日志
                logger.warning(f"发送超时通知失败 task_id={task_id}: {e}")

    def _get_push_service(self):
        """延迟加载 PushService，避免模块导入时循环依赖。

        Returns:
            PushService 实例（测试时可被替换为 Mock）。
        """
        if self._push_service is None:
            from app.services.push_service import get_push_service
            self._push_service = get_push_service()
        return self._push_service


# 全局单例 — 在 FastAPI lifespan 中启动/停止
timeout_monitor = TaskTimeoutMonitor()
