"""Pipeline 进度 WebSocket 推送测试

覆盖范围:
    - _push_pipeline_progress 正常推送（验证 PushService.push 调用参数）
    - _push_pipeline_progress 无事件循环时静默跳过
    - _push_pipeline_progress 推送失败时不影响业务
    - _push_pipeline_progress 消息格式完整性
    - _push_pipeline_progress 无订阅者时不报错
    - WebSocket 端点连接与消息接收
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.pipelines.runner import _push_pipeline_progress


class TestPushPipelineProgress:
    """测试 _push_pipeline_progress 推送函数。"""

    @pytest.mark.asyncio
    async def test_push_calls_push_service_with_correct_channel(self):
        """验证推送消息通过 PushService.push 发送到 pipeline:{run_id} 通道。"""
        mock_service = AsyncMock()
        with patch("app.services.push_service.get_push_service", return_value=mock_service):
            _push_pipeline_progress(1, "signal_gatherer", "running", 0.0, "running")
            await asyncio.sleep(0.05)

        mock_service.push.assert_called_once()
        call_args = mock_service.push.call_args
        assert call_args[0][0] == "pipeline:1"
        data = call_args[0][1]
        assert data["type"] == "pipeline_progress"
        assert data["run_id"] == 1
        assert data["step_name"] == "signal_gatherer"
        assert data["status"] == "running"
        assert data["progress"] == 0.0
        assert data["pipeline_status"] == "running"

    @pytest.mark.asyncio
    async def test_push_channel_isolation(self):
        """验证不同 run_id 推送到不同通道。"""
        mock_service = AsyncMock()
        with patch("app.services.push_service.get_push_service", return_value=mock_service):
            _push_pipeline_progress(1, "step_a", "done", 20.0, "running")
            _push_pipeline_progress(2, "step_b", "running", 0.0, "running")
            await asyncio.sleep(0.05)

        channels = [c[0][0] for c in mock_service.push.call_args_list]
        assert "pipeline:1" in channels
        assert "pipeline:2" in channels

    @pytest.mark.asyncio
    async def test_push_silent_when_no_event_loop(self):
        """验证无事件循环时推送不抛异常（静默跳过）。"""
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("no running loop")):
            _push_pipeline_progress(1, "test", "done", 50.0, "running")

    @pytest.mark.asyncio
    async def test_push_silent_on_service_failure(self):
        """验证 PushService.push 失败时不影响业务。"""
        mock_service = AsyncMock()
        mock_service.push.side_effect = ConnectionError("connection refused")
        with patch("app.services.push_service.get_push_service", return_value=mock_service):
            _push_pipeline_progress(1, "test", "done", 50.0, "running")
            await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_push_message_format(self):
        """验证推送消息包含所有必需字段。"""
        mock_service = AsyncMock()
        with patch("app.services.push_service.get_push_service", return_value=mock_service):
            _push_pipeline_progress(
                run_id=42, step_name="case_generation",
                status="done", progress=60.0, pipeline_status="running",
            )
            await asyncio.sleep(0.05)

        data = mock_service.push.call_args[0][1]
        assert set(data.keys()) == {
            "type", "run_id", "step_name", "status", "progress", "pipeline_status",
        }
        assert data["type"] == "pipeline_progress"
        assert data["run_id"] == 42
        assert data["step_name"] == "case_generation"
        assert data["status"] == "done"
        assert data["progress"] == 60.0
        assert data["pipeline_status"] == "running"

    @pytest.mark.asyncio
    async def test_push_no_subscribers_no_error(self):
        """验证无 WebSocket 订阅者时推送不抛异常。"""
        mock_service = AsyncMock()
        # PushService.push 在无订阅者时返回 False，不抛异常
        mock_service.push.return_value = False
        with patch("app.services.push_service.get_push_service", return_value=mock_service):
            _push_pipeline_progress(999, "test", "done", 100.0, "completed")
            await asyncio.sleep(0.05)


class TestPipelineProgressWebSocketEndpoint:
    """测试 Pipeline 进度 WebSocket 端点。"""

    @pytest.mark.asyncio
    async def test_endpoint_rejects_invalid_token(self, client):
        """验证无效 token 时 WebSocket 连接被拒绝。"""
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/ws/pipeline/1?token=invalid_token"
            ) as ws:
                ws.receive_json()

    @pytest.mark.asyncio
    async def test_endpoint_accepts_valid_token(self, client, authHeaders):
        """验证有效 token 时 WebSocket 连接成功并收到 connected 消息。"""
        token = authHeaders["Authorization"].replace("Bearer ", "")
        with client.websocket_connect(
            f"/api/v1/ws/pipeline/1?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["run_id"] == 1
            assert "Pipeline" in data["message"]

    @pytest.mark.asyncio
    async def test_endpoint_heartbeat(self, client, authHeaders):
        """验证 WebSocket 心跳 ping/pong 机制。"""
        token = authHeaders["Authorization"].replace("Bearer ", "")
        with client.websocket_connect(
            f"/api/v1/ws/pipeline/1?token={token}"
        ) as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"
