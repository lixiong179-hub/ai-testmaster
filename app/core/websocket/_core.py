from typing import Dict, List, Optional
from fastapi import WebSocket
from loguru import logger
from datetime import datetime
import threading


class _CoreMixin:

    async def connect(self, websocket: WebSocket, execution_id: str) -> bool:
        await websocket.accept()

        with self._lock:
            current_connections = len(self.active_connections.get(execution_id, []))
            if current_connections >= self.MAX_CONNECTIONS_PER_EXECUTION:
                logger.warning(f"连接数超限: execution_id={execution_id}, 当前连接数={current_connections}")
                await websocket.close(code=1008, reason="Too many connections")
                return False

            if execution_id not in self.active_connections:
                self.active_connections[execution_id] = []

            self.active_connections[execution_id].append(websocket)
            logger.info(f"WebSocket连接建立: execution_id={execution_id}, 当前连接数={len(self.active_connections[execution_id])}")
            return True

    def disconnect(self, websocket: WebSocket, execution_id: str):
        with self._lock:
            if execution_id in self.active_connections:
                if websocket in self.active_connections[execution_id]:
                    self.active_connections[execution_id].remove(websocket)
                    logger.info(f"WebSocket连接断开: execution_id={execution_id}")

                if not self.active_connections[execution_id]:
                    del self.active_connections[execution_id]

    async def send_message(self, websocket: WebSocket, message: dict) -> bool:
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {e}")
            return False

    async def broadcast(self, execution_id: str, message: dict):
        with self._lock:
            if execution_id not in self.active_connections:
                return
            connections = self.active_connections[execution_id].copy()

        message["timestamp"] = datetime.now().isoformat()

        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket, execution_id)
