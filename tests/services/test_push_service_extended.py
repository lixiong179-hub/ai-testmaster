import pytest
from app.services.push_service import PushService, get_push_service


class TestPushService:
    def test_init(self):
        svc = PushService()
        assert svc._manager is not None

    @pytest.mark.asyncio
    async def test_push_success(self):
        svc = PushService()
        result = await svc.push("task:123", {"status": "running"})
        assert result is True

    @pytest.mark.asyncio
    async def test_push_non_task_channel(self):
        svc = PushService()
        result = await svc.push("custom_channel", {"data": "test"})
        assert result is True


class TestGetPushService:
    def test_returns_instance(self):
        svc = get_push_service()
        assert isinstance(svc, PushService)
