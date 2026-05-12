from __future__ import annotations

"""任务推送Mixin - 处理执行日志和进度的WebSocket实时推送。

本模块实现任务执行过程中的实时消息推送功能，通过PushService
将执行日志和进度信息推送到前端WebSocket客户端。作为Mixin
被TaskService组合使用，实现推送逻辑与执行逻辑的职责分离。

核心类:
    - TaskPushMixin: 任务推送逻辑Mixin

设计模式:
    作为Mixin模块，通过多继承组合到TaskService中，提供:
    - push_execution_log: 推送用例级执行日志
    - push_execution_progress: 推送任务级执行进度

    PushService通过依赖注入方式传入，支持延迟加载，
    避免循环导入问题。

依赖关系:
    - app.services.push_service: WebSocket推送服务

推送数据格式:
    - execution_log: 包含task_id、case_id、level、message、timestamp
    - execution_progress: 包含task_id、status、progress、message、timestamp

容错设计:
    推送失败不影响任务执行，仅记录warning日志。
"""
from datetime import datetime
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from app.services.push_service import PushService


class TaskPushMixin:
    """任务执行日志和进度推送Mixin，依赖注入PushService。

    职责:
        - 推送用例执行日志（info/warning/error级别）
        - 推送任务执行进度（百分比+状态描述）

    设计意图:
        将推送逻辑从执行逻辑中抽离，实现:
        1. 推送失败不影响任务执行
        2. 可替换不同的推送实现（WebSocket/SSE等）
        3. 便于独立测试推送功能

    使用场景:
        被TaskService通过多继承组合，在执行流程中调用推送方法。
    """

    def __init__(self, push_service: 'PushService' = None) -> None:
        """初始化推送Mixin。

        Args:
            push_service: 推送服务实例，可选，支持延迟加载。
        """
        self._push_service = push_service

    def _get_push_service(self) -> 'PushService':
        """获取推送服务实例，采用延迟加载模式。

        首次调用时从push_service模块获取实例并缓存，
        避免模块初始化时的循环导入问题。

        Returns:
            PushService实例。
        """
        if self._push_service is None:
            from app.services.push_service import get_push_service
            self._push_service = get_push_service()
        return self._push_service

    async def push_execution_log(
        self,
        task_id: int,
        case_id: int,
        level: str,
        message: str
    ) -> None:
        """推送用例执行日志，包含任务ID、用例ID、日志级别和消息内容。

        日志数据结构:
            {
                "type": "execution_log",
                "task_id": int,
                "case_id": int,
                "level": "info" | "warning" | "error",
                "message": str,
                "timestamp": ISO格式时间戳
            }

        Args:
            task_id: 任务ID，用于确定推送通道。
            case_id: 用例ID，标识日志来源用例。
            level: 日志级别，如info/warning/error。
            message: 日志消息内容。

        Note:
            推送失败仅记录warning日志，不影响任务执行流程。
        """
        try:
            log_data = {
                "type": "execution_log",
                "task_id": task_id,
                "case_id": case_id,
                "level": level,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            await self._get_push_service().push(f"task:{task_id}", log_data)
        except Exception as e:
            # 推送失败不影响任务执行，仅记录警告
            logger.warning(f"推送执行日志失败: {e}")

    async def push_execution_progress(
        self,
        task_id: int,
        status: str,
        progress: int,
        message: str
    ) -> None:
        """推送任务执行进度，包含状态、百分比和当前阶段描述。

        进度数据结构:
            {
                "type": "execution_progress",
                "task_id": int,
                "status": "running" | "completed" | "failed" | "stopped",
                "progress": 0-100,
                "message": str,
                "timestamp": ISO格式时间戳
            }

        Args:
            task_id: 任务ID，用于确定推送通道。
            status: 执行状态，如running/completed/failed/stopped。
            progress: 进度百分比(0-100)。
            message: 当前阶段描述，如"已完成 3/10"。

        Note:
            推送失败仅记录warning日志，不影响任务执行流程。
        """
        try:
            progress_data = {
                "type": "execution_progress",
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            await self._get_push_service().push(f"task:{task_id}", progress_data)
        except Exception as e:
            # 推送失败不影响任务执行，仅记录警告
            logger.warning(f"推送执行进度失败: {e}")
