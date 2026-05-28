"""
WebSocket API端点

用于实时推送测试执行状态
"""
import asyncio
"""
WebSocket端点模块

本模块定义WebSocket连接端点，用于实时推送测试执行进度和日志信息。

路由前缀: /ws
标签: WebSocket

端点概览:
    - WS /execution/{execution_id} - 测试执行实时进度推送
    - WS /pipeline/{run_id} - Pipeline运行进度实时推送
    - WS /logs - 实时日志推送

权限要求: WebSocket连接需通过查询参数传递token进行认证

业务说明:
    - 执行进度推送包含步骤状态变更、截图更新等事件
    - Pipeline进度推送包含Step状态变更和整体进度
    - 连接断开后自动重连
    - 心跳检测间隔30秒
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.websocket import manager
from app.utils.jwt_utils import decode_token
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/execution/{execution_id}")
async def execution_websocket(
    websocket: WebSocket, 
    execution_id: str,
    token: str = Query(..., description="JWT Token用于身份验证")
):
    """
    WebSocket连接端点 - 用于实时接收测试执行状态
    
    连接URL: ws://host/api/v1/ws/execution/{execution_id}?token=xxx
    
    消息格式:
    - 日志消息: {"type": "log", "step_number": 1, "action": "点击按钮", "status": "success", "message": ""}
    - 截图消息: {"type": "screenshot", "step_number": 1, "screenshot": "base64...", "highlight_region": {...}}
    - 进度消息: {"type": "progress", "current_step": 1, "total_steps": 5, "percentage": 20.0}
    - 状态消息: {"type": "status", "status": "running", "message": "执行中"}
    
    Args:
        websocket: WebSocket对象
        execution_id: 执行ID
        token: JWT Token
    """
    # 验证token
    try:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=1008, reason="Token validation failed")
        return
    
    # 建立连接（带连接数限制检查）
    connected = await manager.connect(websocket, execution_id)
    if not connected:
        return  # 连接数超限，已自动关闭
    
    try:
        # 发送连接成功消息
        success = await manager.send_message(websocket, {
            "type": "connected",
            "execution_id": execution_id,
            "message": "WebSocket连接成功"
        })
        
        if not success:
            manager.disconnect(websocket, execution_id)
            return
        
        # 保持连接，接收客户端消息
        while True:
            try:
                # 接收客户端消息（带30秒超时）
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await manager.send_message(websocket, {
                        "type": "error",
                        "message": "Invalid JSON format"
                    })
                    continue
                
                # 处理心跳
                if message.get("type") == "ping":
                    success = await manager.send_message(websocket, {"type": "pong"})
                    if not success:
                        break  # 发送失败，退出循环
                
                # 处理其他客户端消息
                elif message.get("type") == "subscribe":
                    # 客户端订阅特定消息类型
                    await manager.send_message(websocket, {
                        "type": "subscribed",
                        "channels": message.get("channels", [])
                    })
                
                elif message.get("type") == "close":
                    # 客户端主动关闭
                    break
                    
            except asyncio.TimeoutError:
                # 超时，发送心跳检测
                success = await manager.send_message(websocket, {"type": "ping"})
                if not success:
                    break  # 发送失败，退出循环
                
    except WebSocketDisconnect:
        logger.debug("WebSocket连接断开")
    except Exception:
        logger.debug("WebSocket连接异常", exc_info=True)
    finally:
        manager.disconnect(websocket, execution_id)


@router.websocket("/ws/pipeline/{run_id}")
async def pipeline_progress_websocket(
    websocket: WebSocket,
    run_id: int,
    token: str = Query(..., description="JWT Token用于身份验证"),
):
    """WebSocket连接端点 - 用于实时接收Pipeline运行进度。

    连接URL: ws://host/api/v1/ws/pipeline/{run_id}?token=xxx

    消息格式:
    - 进度消息: {"type": "pipeline_progress", "run_id": 1,
        "step_name": "signal_gatherer", "status": "done",
        "progress": 20.0, "pipeline_status": "running"}
    - 连接成功: {"type": "connected", "run_id": 1,
        "message": "Pipeline进度WebSocket连接成功"}

    Args:
        websocket: WebSocket对象
        run_id: Pipeline运行ID
        token: JWT Token
    """
    try:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=1008, reason="Token validation failed")
        return

    channel_id = f"pipeline:{run_id}"

    connected = await manager.connect(websocket, channel_id)
    if not connected:
        return

    try:
        success = await manager.send_message(websocket, {
            "type": "connected",
            "run_id": run_id,
            "message": "Pipeline进度WebSocket连接成功",
        })
        if not success:
            manager.disconnect(websocket, channel_id)
            return

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0,
                )
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await manager.send_message(websocket, {
                        "type": "error",
                        "message": "Invalid JSON format",
                    })
                    continue

                if message.get("type") == "ping":
                    success = await manager.send_message(websocket, {"type": "pong"})
                    if not success:
                        break
                elif message.get("type") == "close":
                    break

            except asyncio.TimeoutError:
                success = await manager.send_message(websocket, {"type": "ping"})
                if not success:
                    break

    except WebSocketDisconnect:
        logger.debug("Pipeline进度WebSocket连接断开")
    except Exception:
        logger.debug("Pipeline进度WebSocket连接异常", exc_info=True)
    finally:
        manager.disconnect(websocket, channel_id)


@router.get("/ws/stats")
async def get_websocket_stats() -> dict:
    """
    获取WebSocket连接统计
    
    Returns:
        连接统计信息
    """
    return {
        "total_connections": manager.get_connection_count(),
        "active_executions": len(manager.active_connections),
        "executions": {
            execution_id: len(connections)
            for execution_id, connections in manager.active_connections.items()
        }
    }
