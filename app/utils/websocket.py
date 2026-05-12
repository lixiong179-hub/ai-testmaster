"""
WebSocket连接管理模块

提供基于FastAPI WebSocket的连接管理功能，支持任务级别的消息广播。
主要用于AI分析/生成任务的实时进度推送。

连接管理模型：
    以任务（task_id）为维度组织连接，同一任务下按用户（user_id）区分连接。
    结构：{task_id: {user_id: websocket}}

    典型场景：多个用户同时查看同一任务的执行进度时，
    每个用户建立独立的WebSocket连接，任务进度更新时广播给该任务的所有连接。

核心类：
    - ConnectionManager: WebSocket连接管理器

全局实例：
    - manager: 全局连接管理器单例

依赖：
    - fastapi.WebSocket: WebSocket连接对象
    - loguru.logger: 日志记录
"""
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class ConnectionManager:
    """WebSocket连接管理器

    管理任务维度的WebSocket连接，支持连接建立、断开、
    个人消息发送和任务级广播。

    数据结构：
        active_connections: Dict[int, Dict[int, WebSocket]]
        外层key为task_id，内层key为user_id，value为WebSocket连接实例

    线程安全说明：
        当前实现依赖FastAPI的异步事件循环，在单线程asyncio环境下安全。
        若需多worker部署，应替换为Redis Pub/Sub等分布式方案。
    """

    def __init__(self):
        # 存储活动的WebSocket连接
        # 格式: {task_id: {user_id: websocket}}
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: int, user_id: int):
        """
        建立WebSocket连接
        
        Args:
            websocket: WebSocket连接
            task_id: 任务ID
            user_id: 用户ID
        """
        await websocket.accept()
        
        if task_id not in self.active_connections:
            self.active_connections[task_id] = {}
        
        self.active_connections[task_id][user_id] = websocket
        logger.info(f"WebSocket连接建立: 任务 {task_id}, 用户 {user_id}")
    
    def disconnect(self, task_id: int, user_id: int):
        """
        断开WebSocket连接
        
        Args:
            task_id: 任务ID
            user_id: 用户ID
        """
        if task_id in self.active_connections:
            if user_id in self.active_connections[task_id]:
                del self.active_connections[task_id][user_id]
                logger.info(f"WebSocket连接断开: 任务 {task_id}, 用户 {user_id}")
            
            # 如果任务没有活跃连接，删除任务条目
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """
        发送个人消息
        
        Args:
            message: 消息内容
            websocket: WebSocket连接
        """
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.error("WebSocket连接已断开，无法发送消息")
    
    async def broadcast(self, message: Dict[str, Any], task_id: int):
        """广播消息给指定任务的所有连接

        向同一任务下的所有WebSocket连接发送消息。
        发送失败的连接（已断开）会被自动清理。

        Args:
            message: 消息内容字典，将被序列化为JSON发送
            task_id: 目标任务ID
        """
        if task_id in self.active_connections:
            disconnected_users = []

            for user_id, websocket in self.active_connections[task_id].items():
                try:
                    await websocket.send_json(message)
                except WebSocketDisconnect:
                    # 记录断开的连接，广播完成后统一清理
                    disconnected_users.append(user_id)
                    logger.error(f"WebSocket连接已断开: 任务 {task_id}, 用户 {user_id}")
                except Exception as e:
                    logger.error(f"发送消息失败: 任务 {task_id}, 用户 {user_id}, 错误: {e}")

            # 清理断开的连接，避免内存泄漏
            for user_id in disconnected_users:
                self.disconnect(task_id, user_id)


# 全局连接管理器单例 — 整个应用共享同一实例
manager = ConnectionManager()
