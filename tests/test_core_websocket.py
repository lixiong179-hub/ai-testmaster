import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket

from app.core.websocket import ConnectionManager, manager


class TestConnectionManagerInit:
    def test_empty_connections(self):
        mgr = ConnectionManager()
        assert mgr.active_connections == {}

    def test_has_lock(self):
        mgr = ConnectionManager()
        assert mgr._lock is not None

    def test_max_connections_constant(self):
        assert ConnectionManager.MAX_CONNECTIONS_PER_EXECUTION == 10


class TestConnectionManagerConnect:
    @pytest.mark.asyncio
    async def test_connect_success(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        result = await mgr.connect(ws, "exec-1")
        assert result is True
        assert ws in mgr.active_connections["exec-1"]
        ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple_same_execution(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        assert len(mgr.active_connections["exec-1"]) == 2

    @pytest.mark.asyncio
    async def test_connect_different_executions(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-2")
        assert "exec-1" in mgr.active_connections
        assert "exec-2" in mgr.active_connections

    @pytest.mark.asyncio
    async def test_connect_exceeds_limit(self):
        mgr = ConnectionManager()
        mgr.MAX_CONNECTIONS_PER_EXECUTION = 2
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        ws3 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-limit")
        await mgr.connect(ws2, "exec-limit")
        result = await mgr.connect(ws3, "exec-limit")
        assert result is False
        ws3.close.assert_called_once_with(code=1008, reason="Too many connections")
        mgr.MAX_CONNECTIONS_PER_EXECUTION = 10

    @pytest.mark.asyncio
    async def test_connect_empty_execution_id(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        result = await mgr.connect(ws, "")
        assert result is True
        assert "" in mgr.active_connections


class TestConnectionManagerDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        mgr.disconnect(ws, "exec-1")
        assert "exec-1" not in mgr.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_last_connection_cleans_key(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        mgr.disconnect(ws, "exec-1")
        assert "exec-1" not in mgr.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_keeps_remaining_connections(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        mgr.disconnect(ws1, "exec-1")
        assert "exec-1" in mgr.active_connections
        assert len(mgr.active_connections["exec-1"]) == 1
        assert ws2 in mgr.active_connections["exec-1"]

    def test_disconnect_nonexistent_execution(self):
        mgr = ConnectionManager()
        ws = MagicMock(spec=WebSocket)
        mgr.disconnect(ws, "nonexistent")
        assert "nonexistent" not in mgr.active_connections

    def test_disconnect_nonexistent_websocket(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = MagicMock(spec=WebSocket)
        mgr.active_connections["exec-1"] = [ws1]
        mgr.disconnect(ws2, "exec-1")
        assert len(mgr.active_connections["exec-1"]) == 1


class TestConnectionManagerSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        result = await mgr.send_message(ws, {"type": "test"})
        assert result is True
        ws.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        ws.send_json.side_effect = Exception("connection closed")
        result = await mgr.send_message(ws, {"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_empty_dict(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        result = await mgr.send_message(ws, {})
        assert result is True


class TestConnectionManagerBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_to_all_connections(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        await mgr.broadcast("exec-1", {"type": "status", "status": "running"})
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_adds_timestamp(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.broadcast("exec-1", {"type": "log"})
        call_args = ws.send_json.call_args[0][0]
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_broadcast_nonexistent_execution(self):
        mgr = ConnectionManager()
        await mgr.broadcast("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_cleans_disconnected(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        ws1.send_json.side_effect = Exception("disconnected")
        await mgr.broadcast("exec-1", {"type": "test"})
        assert ws1 not in mgr.active_connections["exec-1"]
        assert ws2 in mgr.active_connections["exec-1"]


class TestConnectionManagerSendLog:
    @pytest.mark.asyncio
    async def test_send_log(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_log("exec-1", step_number=1, action="点击按钮", status="success", message="ok")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "log"
        assert call_args["step_number"] == 1
        assert call_args["action"] == "点击按钮"
        assert call_args["status"] == "success"
        assert call_args["message"] == "ok"

    @pytest.mark.asyncio
    async def test_send_log_default_message(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_log("exec-1", step_number=2, action="输入", status="running")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["message"] == ""


class TestConnectionManagerSendScreenshot:
    @pytest.mark.asyncio
    async def test_send_screenshot_without_highlight(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_screenshot("exec-1", step_number=1, screenshot_base64="base64data")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "screenshot"
        assert call_args["screenshot"] == "base64data"
        assert "highlight_region" not in call_args

    @pytest.mark.asyncio
    async def test_send_screenshot_with_highlight(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        highlight = {"x": 100, "y": 200, "width": 50, "height": 30}
        await mgr.send_screenshot("exec-1", step_number=1, screenshot_base64="data", highlight_region=highlight)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["highlight_region"] == highlight

    @pytest.mark.asyncio
    async def test_send_screenshot_none_highlight(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_screenshot("exec-1", step_number=1, screenshot_base64="data", highlight_region=None)
        call_args = ws.send_json.call_args[0][0]
        assert "highlight_region" not in call_args


class TestConnectionManagerSendProgress:
    @pytest.mark.asyncio
    async def test_send_progress_without_estimate(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_progress("exec-1", current_step=3, total_steps=10)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "progress"
        assert call_args["current_step"] == 3
        assert call_args["total_steps"] == 10
        assert call_args["percentage"] == 30.0
        assert "estimated_remaining_seconds" not in call_args

    @pytest.mark.asyncio
    async def test_send_progress_with_estimate(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_progress("exec-1", current_step=5, total_steps=10, estimated_remaining_seconds=30)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["estimated_remaining_seconds"] == 30
        assert call_args["percentage"] == 50.0

    @pytest.mark.asyncio
    async def test_send_progress_zero_steps_raises(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        with pytest.raises(ZeroDivisionError):
            await mgr.send_progress("exec-1", current_step=0, total_steps=0)

    @pytest.mark.asyncio
    async def test_send_progress_percentage_precision(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_progress("exec-1", current_step=2, total_steps=3)
        call_args = ws.send_json.call_args[0][0]
        assert call_args["percentage"] == 66.7


class TestConnectionManagerSendStatus:
    @pytest.mark.asyncio
    async def test_send_status(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_status("exec-1", status="started", message="测试开始")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["type"] == "status"
        assert call_args["status"] == "started"
        assert call_args["message"] == "测试开始"

    @pytest.mark.asyncio
    async def test_send_status_default_message(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_status("exec-1", status="completed")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["message"] == ""

    @pytest.mark.asyncio
    async def test_send_status_failed(self):
        mgr = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await mgr.connect(ws, "exec-1")
        await mgr.send_status("exec-1", status="failed", message="超时")
        call_args = ws.send_json.call_args[0][0]
        assert call_args["status"] == "failed"


class TestConnectionManagerGetConnectionCount:
    @pytest.mark.asyncio
    async def test_count_specific_execution(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        assert mgr.get_connection_count("exec-1") == 2

    @pytest.mark.asyncio
    async def test_count_nonexistent_execution(self):
        mgr = ConnectionManager()
        assert mgr.get_connection_count("nonexistent") == 0

    @pytest.mark.asyncio
    async def test_count_total_connections(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        ws3 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        await mgr.connect(ws3, "exec-2")
        assert mgr.get_connection_count() == 3

    def test_count_empty_manager(self):
        mgr = ConnectionManager()
        assert mgr.get_connection_count() == 0
        assert mgr.get_connection_count("any") == 0

    @pytest.mark.asyncio
    async def test_count_after_disconnect(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await mgr.connect(ws1, "exec-1")
        await mgr.connect(ws2, "exec-1")
        mgr.disconnect(ws1, "exec-1")
        assert mgr.get_connection_count("exec-1") == 1


class TestGlobalManager:
    def test_manager_is_connection_manager(self):
        assert isinstance(manager, ConnectionManager)

    def test_manager_is_singleton(self):
        from app.core.websocket import manager as manager2
        assert manager is manager2
