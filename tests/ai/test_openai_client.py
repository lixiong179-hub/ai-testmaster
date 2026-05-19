"""OpenAIClient 真实 API 测试

使用真实 DeepSeek API 调用，禁歿Mock〿测试范围：构造函数、complate 调用、系统提示、异常路径〿"""
import os
import pytest
from app.ai.client import AIResponse, TokenUsage
from app.ai.openai_client import OpenAIClient
from app.core.config import settings

_SKIP_REASON = None
if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY.startswith("your"):
    _SKIP_REASON = "未配罿DeepSeek API Key"
elif os.environ.get("CI") == "true" and not os.environ.get("RUN_REAL_AI_TESTS"):
    _SKIP_REASON = "CI 环境跳过真实 AI 调用"

pytestmark = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "unknown")


class TestOpenAIClientInit:
    def test_init_with_defaults(self):
        client = OpenAIClient()
        assert client.model == settings.AI_MODEL_NAME
        assert client.temperature == settings.AI_TEMPERATURE
        assert client.max_tokens == settings.AI_MAX_TOKENS
        assert client.max_retries == 3

    def test_init_with_custom_params(self):
        client = OpenAIClient(
            model="custom-model",
            temperature=0.5,
            max_tokens=512,
            max_retries=5,
        )
        assert client.model == "custom-model"
        assert client.temperature == 0.5
        assert client.max_tokens == 512
        assert client.max_retries == 5

    def test_init_with_only_model(self):
        client = OpenAIClient(model="gpt-4")
        assert client.model == "gpt-4"

    def test_lazy_client_not_created_on_init(self):
        client = OpenAIClient()
        assert client._client is None


class TestOpenAIClientLazyClient:
    def test_client_property_creates_instance(self):
        client = OpenAIClient()
        c = client.client
        assert c is not None
        assert client._client is not None

    def test_client_property_returns_same_instance(self):
        client = OpenAIClient()
        c1 = client.client
        c2 = client.client
        assert c1 is c2


@pytest.mark.real_api
class TestOpenAIClientComplete:
    def test_complete_simple_returns_response(self):
        client = OpenAIClient()
        response = client.complete("Say 'hello' in exactly one word.")
        assert isinstance(response, AIResponse)
        assert len(response.content) > 0
        assert response.model_version != ""
        assert response.latency_ms > 0

    def test_complete_with_system_prompt(self):
        client = OpenAIClient()
        response = client.complete(
            prompt="What is 2+2? Reply with just the number.",
            system="You are a helpful math assistant.",
        )
        assert isinstance(response, AIResponse)
        assert len(response.content) > 0

    def test_complete_usage_tokens_positive(self):
        client = OpenAIClient()
        response = client.complete("Count from 1 to 5.")
        assert response.usage.prompt_tokens > 0
        assert response.usage.completion_tokens > 0

    def test_complete_temperature_override(self):
        client = OpenAIClient()
        response = client.complete(
            "Say the word 'test'.",
            temperature=0.0,
        )
        assert isinstance(response, AIResponse)

    def test_complete_max_tokens_override(self):
        client = OpenAIClient()
        response = client.complete(
            "Write a short sentence.",
            max_tokens=10,
        )
        assert isinstance(response, AIResponse)
        assert response.usage.completion_tokens <= 10

    def test_complete_with_schema_parses_json(self):
        client = OpenAIClient()
        schema = {
            "type": "object",
            "properties": {
                "word": {"type": "string"},
                "length": {"type": "integer"},
            },
            "required": ["word", "length"],
        }
        response = client.complete(
            "Output a JSON with a random word and its length.",
            schema=schema,
        )
        assert response.parsed is not None
        assert "word" in response.parsed
        assert "length" in response.parsed

    def test_complete_latency_reasonable(self):
        client = OpenAIClient()
        response = client.complete("Hi")
        assert 0 < response.latency_ms < 60000


@pytest.mark.real_api
class TestOpenAIClientEdgeCases:
    def test_complete_empty_prompt(self):
        client = OpenAIClient()
        response = client.complete(" ")
        assert isinstance(response, AIResponse)

    def test_complete_system_only_no_user_content(self):
        client = OpenAIClient()
        response = client.complete(
            prompt="Say yes.",
            system="You must reply only with 'yes'.",
        )
        assert isinstance(response, AIResponse)

    def test_complete_with_metadata(self):
        client = OpenAIClient()
        response = client.complete(
            prompt="Say 'OK'.",
            metadata={"step_name": "test_step", "run_id": "test-001"},
        )
        assert isinstance(response, AIResponse)

    def test_complete_not_degraded(self):
        client = OpenAIClient()
        response = client.complete("Say hello.")
        assert response.degraded is False
