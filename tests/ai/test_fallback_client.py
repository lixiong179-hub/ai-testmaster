"""FallbackAIClient 主备切换测试

使用真实客户端验证主备切换逻辑：坏 key 主模垿↿真实 key 备用模型〿禁止 Mock，通过构造失效主客户端实现真实故障场景〿"""
import os
import pytest
from app.ai.client import AIResponse
from app.ai.openai_client import OpenAIClient
from app.ai.fallback_client import FallbackAIClient
from app.core.config import settings

_SKIP_REASON = None
if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY.startswith("your"):
    _SKIP_REASON = "未配罿DeepSeek API Key"
elif os.environ.get("CI") == "true" and not os.environ.get("RUN_REAL_AI_TESTS"):
    _SKIP_REASON = "CI 环境跳过真实 AI 调用"

pytestmark = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "unknown")

_BAD_CLIENT = OpenAIClient(api_key="sk-invalid-key-for-testing", max_retries=0)
_REAL_CLIENT = OpenAIClient(max_retries=1)


class TestFallbackAIClientInit:
    def test_initial_state(self):
        fc = FallbackAIClient(primary=_BAD_CLIENT, fallback=_REAL_CLIENT)
        assert fc.failure_count == 0
        assert fc.switched is False
        assert fc.max_failures == 3

    def test_custom_max_failures(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=2,
        )
        assert fc.max_failures == 2

    def test_primary_fallback_assigned(self):
        fc = FallbackAIClient(primary=_BAD_CLIENT, fallback=_REAL_CLIENT)
        assert fc.primary is _BAD_CLIENT
        assert fc.fallback is _REAL_CLIENT


class TestFallbackAIClientReset:
    def test_reset_after_failure(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=2,
        )
        try:
            fc.complete("hi")
        except Exception:
            pass
        assert fc.failure_count == 1
        fc.reset()
        assert fc.failure_count == 0
        assert fc.switched is False

    def test_reset_after_switch(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=1,
        )
        response = fc.complete("Say hi.")
        assert fc.switched is True
        fc.reset()
        assert fc.failure_count == 0
        assert fc.switched is False


@pytest.mark.real_api
class TestFallbackAIClientSwitchBehavior:
    def test_switches_after_max_failures(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=1,
        )
        response = fc.complete("Say hello in one word.")
        assert isinstance(response, AIResponse)
        assert response.degraded is True
        assert fc.switched is True
        assert fc.failure_count == 1

    def test_switched_directly_uses_fallback(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=1,
        )
        fc.complete("First call.")
        assert fc.switched is True
        response = fc.complete("Second call.")
        assert isinstance(response, AIResponse)
        assert response.degraded is True

    def test_accumulates_failure_before_switch(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=2,
        )
        with pytest.raises(Exception):
            fc.complete("Call 1")
        assert fc.failure_count == 1
        assert fc.switched is False
        response = fc.complete("Call 2")
        assert fc.switched is True
        assert response.degraded is True

    def test_fallback_response_has_content(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=1,
        )
        response = fc.complete("Say 'OK'.")
        assert len(response.content) > 0
        assert response.model_version != ""


@pytest.mark.real_api
class TestFallbackAIClientEdgeCases:
    def test_multiple_calls_after_switch(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=1,
        )
        fc.complete("Call 1")
        for i in range(3):
            response = fc.complete(f"Call {i + 2}")
            assert response.degraded is True

    def test_reset_and_reuse(self):
        fc = FallbackAIClient(
            primary=_BAD_CLIENT,
            fallback=_REAL_CLIENT,
            max_failures=1,
        )
        fc.complete("First switch")
        fc.reset()
        response = fc.complete("After reset")
        assert response.degraded is True
        assert fc.switched is True
