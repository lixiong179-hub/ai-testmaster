"""推送服务单元测�?""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.push_service import PushService, get_push_service


class TestPushService:
    def test_init(self):
        svc = PushService()
        assert svc._manager is not None

    @pytest.mark.asyncio
    async def test_push_task_channel(self):
        svc = PushService()
        svc._manager = MagicMock()
        svc._manager.broadcast = AsyncMock()
        result = await svc.push("task:123", {"status": "running"})
        assert result is True
        svc._manager.broadcast.assert_called_once_with("123", {"status": "running"})

    @pytest.mark.asyncio
    async def test_push_non_task_channel(self):
        svc = PushService()
        svc._manager = MagicMock()
        svc._manager.broadcast = AsyncMock()
        result = await svc.push("custom_channel", {"data": 1})
        assert result is True
        svc._manager.broadcast.assert_called_once_with("custom_channel", {"data": 1})

    @pytest.mark.asyncio
    async def test_push_failure_returns_false(self):
        svc = PushService()
        svc._manager = MagicMock()
        svc._manager.broadcast = AsyncMock(side_effect=Exception("connection lost"))
        result = await svc.push("task:1", {"status": "fail"})
        assert result is False


class TestGetPushService:
    def test_returns_instance(self):
        svc = get_push_service()
        assert isinstance(svc, PushService)

    def test_returns_new_instance(self):
        svc1 = get_push_service()
        svc2 = get_push_service()
        assert svc1 is not svc2
