"""task_assembler 后台执行与终态推送子模块。

从 task_assembler.py 拆分而来，包含 _run_executor_safely（后台执行引擎
+ 异常兜底）与 _push_final_status（执行完成后推送终态到 WebSocket 通道）
两个 async 函数。所有函数均为模块级纯函数，接受依赖参数。

业务原因：task_assembler.py 单文件超过 350 行限制，按职责将后台执行
与终态推送逻辑集中到独立文件，主类聚焦于任务创建与编排。
"""
from typing import Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_task import TaskStatus, TestTask
from app.services.push_service import PushService
from app.services.test_execution_engine_v2 import TestExecutionEngineV2
from app.utils.db_time import utcnow


async def run_executor_safely(
    task_id: int,
    executor_factory: Callable[[Session], TestExecutionEngineV2],
    push_service: PushService,
) -> None:
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
        executor = executor_factory(session)
        await executor.execute_test_task(
            task_id=task_id, execution_mode="smart"
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
        await push_final_status(task_id, session, push_service)
        session.close()


async def push_final_status(
    task_id: int,
    session: Session,
    push_service: PushService,
) -> None:
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
        channel = f"quick_test:{task_id}"
        if task.status == TaskStatus.COMPLETED:
            await push_service.push(channel, {
                "stage": "completed", "status": "done", "progress": 100,
                "detail": {"task_id": task_id},
            })
        elif task.status == TaskStatus.FAILED:
            await push_service.push(channel, {
                "stage": "failed", "status": "error", "progress": 100,
                "detail": {"message": "执行失败", "task_id": task_id},
            })
        elif task.status == TaskStatus.STOPPED:
            await push_service.push(channel, {
                "stage": "stopped", "status": "done", "progress": 100,
                "detail": {"message": "任务已停止", "task_id": task_id},
            })
    except Exception as exc:
        logger.warning(f"终态推送失败: task_id={task_id} err={exc}")


__all__ = [
    "_CHANNEL_TEMPLATE",
    "run_executor_safely",
    "push_final_status",
]
