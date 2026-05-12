"""推送服务模块 - WebSocket消息推送，实现任务执行状态的实时通信。

本模块封装WebSocket消息推送能力，通过ConnectionManager将任务执行
状态、日志和进度信息实时广播到前端客户端。推送服务采用依赖注入
方式被TaskPushMixin等模块使用。

核心类:
    - PushService: WebSocket推送服务

核心函数:
    - get_push_service: 工厂函数，获取PushService实例

依赖关系:
    - app.core.websocket: WebSocket连接管理器(ConnectionManager)

设计说明:
    PushService作为推送层的统一抽象，屏蔽底层WebSocket实现细节。
    通道命名规范为"task:{task_id}"，内部转换为execution_id进行广播。
    推送失败不抛出异常，仅记录warning日志，确保不影响业务流程。

    get_push_service工厂函数遵循依赖注入原则，避免调用方直接new实例，
    便于测试时替换Mock实现。
"""
from typing import Any, Dict
from loguru import logger

from app.core.websocket import manager as ws_manager


class PushService:
    """WebSocket消息推送服务，通过ConnectionManager广播任务执行状态。

    职责:
        - 向指定通道推送JSON序列化消息
        - 处理通道标识符格式转换
        - 推送失败时优雅降级（记录日志，不抛异常）

    使用场景:
        - 任务执行过程中推送进度更新
        - 用例执行过程中推送日志信息
        - 任务状态变更时推送通知

    设计意图:
        作为推送层的统一抽象，屏蔽WebSocket底层实现。
        调用方只需指定通道和数据，无需关心连接管理细节。
    """

    def __init__(self) -> None:
        """初始化推送服务，注入WebSocket连接管理器。"""
        self._manager = ws_manager

    async def push(self, channel: str, data: Dict[str, Any]) -> bool:
        """向指定通道推送消息，失败时返回False并记录警告日志。

        通道格式转换:
            "task:{task_id}" -> "{task_id}"
            其他格式保持不变

        Args:
            channel: 通道标识符，格式为"task:{task_id}"。
            data: 待推送的字典数据，需为JSON可序列化类型。

        Returns:
            推送成功返回True，失败返回False。

        Note:
            推送失败不抛出异常，确保不影响业务主流程。
        """
        try:
            # 将"task:{id}"格式转换为execution_id，与ConnectionManager对接
            execution_id = channel.replace("task:", "") if channel.startswith("task:") else channel
            await self._manager.broadcast(execution_id, data)
            return True
        except Exception as e:
            logger.warning(f"推送消息失败: channel={channel}, 错误: {e}")
            return False


def get_push_service() -> PushService:
    """获取PushService实例的工厂函数。

    遵循依赖注入原则，避免调用方直接new实例。
    测试时可通过Mock替换此函数返回值。

    Returns:
        PushService实例。
    """
    return PushService()
