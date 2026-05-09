"""AI Client 数据类单元测�?
覆盖 TokenUsage、AIResponse 数据类的创建、默认值、边界场景�?"""
import pytest

from app.ai.client import TokenUsage, AIResponse


class TestTokenUsage:
    def test_create_with_defaults(self):
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_cost_usd == 0.0

    def test_create_with_values(self):
        usage = TokenUsage(
            prompt_tokens=150,
            completion_tokens=80,
            total_cost_usd=0.00043,
        )
        assert usage.prompt_tokens == 150
        assert usage.completion_tokens == 80
        assert usage.total_cost_usd == 0.00043

    def test_zero_cost(self):
        usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_cost_usd=0.0)
        assert usage.total_cost_usd == 0.0

    def test_large_token_values(self):
        usage = TokenUsage(
            prompt_tokens=100000,
            completion_tokens=50000,
            total_cost_usd=0.35,
        )
        assert usage.prompt_tokens == 100000
        assert usage.completion_tokens == 50000


class TestAIResponse:
    def test_create_with_defaults(self):
        response = AIResponse()
        assert response.content == ""
        assert response.parsed is None
        assert response.model_version == ""
        assert response.latency_ms == 0
        assert response.degraded is False
        assert isinstance(response.usage, TokenUsage)
        assert response.raw_response is None

    def test_create_with_content(self):
        response = AIResponse(content="Hello, world!")
        assert response.content == "Hello, world!"

    def test_create_with_parsed_json(self):
        response = AIResponse(
            content='{"key": "value"}',
            parsed={"key": "value"},
        )
        assert response.parsed == {"key": "value"}

    def test_create_with_usage_and_model(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_cost_usd=0.00004)
        response = AIResponse(
            content="test",
            usage=usage,
            model_version="deepseek-v4-flash",
            latency_ms=350,
        )
        assert response.usage.prompt_tokens == 10
        assert response.model_version == "deepseek-v4-flash"
        assert response.latency_ms == 350

    def test_create_degraded_response(self):
        response = AIResponse(content="fallback answer", degraded=True)
        assert response.degraded is True
        assert response.content == "fallback answer"

    def test_create_with_raw_response(self):
        raw = {"id": "chatcmpl-123", "object": "chat.completion"}
        response = AIResponse(content="ok", raw_response=raw)
        assert response.raw_response == raw

    def test_parsed_empty_dict(self):
        response = AIResponse(content="{}", parsed={})
        assert response.parsed == {}

    def test_parsed_none_string(self):
        response = AIResponse(content="null", parsed=None)
        assert response.parsed is None
