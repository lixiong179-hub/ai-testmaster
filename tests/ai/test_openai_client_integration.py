"""
M1-T08 OpenAI Client 真实 API 集成测试

使用真实 DeepSeek API 调用验证 OpenAIClient。
需要 DEEPSEEK_API_KEY 环境变量配置。

运行方式：
    pytest tests/ai/test_openai_client_integration.py -v -s --no-cov

注意：此测试会产生实际 API 调用费用，默认不纳入 CI。
"""
import json
import os

import pytest

# 注意：不可在模块顶部调用 load_dotenv() — 会在测试收集阶段将 .env 中的
# CORS_ORIGINS=* 等变量注入 os.environ，污染后续测试（如 test_core_config.py
# 的 DevSettings 默认值校验）。改为在 fixture 内按需加载。

from app.ai.client import AIResponse, TokenUsage
from app.ai.openai_client import OpenAIClient


# 仅在 API Key 可用时运行
pytestmark = pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set, skipping real API integration test",
)


@pytest.fixture
def openai_client():
    from dotenv import load_dotenv
    load_dotenv()  # 从 .env 加载 DEEPSEEK_API_KEY（仅在 fixture 实际执行时）
    return OpenAIClient()


class TestOpenAIClientRealAPI:
    """真实 API 调用集成测试"""

    def test_basic_complete(self, openai_client):
        """基本文本补全"""
        resp = openai_client.complete(
            "请用一句话回答：1+1等于几？",
            metadata={"step_name": "integration_test"},
        )
        assert isinstance(resp, AIResponse)
        assert resp.content
        assert "2" in resp.content
        assert resp.model_version
        assert resp.latency_ms > 0
        assert resp.usage.prompt_tokens > 0
        assert resp.usage.completion_tokens > 0
        assert resp.usage.total_cost_usd > 0
        assert resp.degraded is False

    def test_with_system_prompt(self, openai_client):
        """带 system prompt 的调用"""
        resp = openai_client.complete(
            "什么是测试用例？",
            system="你是一个专业的软件测试工程师，回答要简洁专业。",
            metadata={"step_name": "integration_test"},
        )
        assert resp.content
        assert resp.usage.prompt_tokens > 0

    def test_with_schema_json_output(self, openai_client):
        """带 JSON Schema 约束的调用"""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["name", "priority"],
        }
        resp = openai_client.complete(
            "生成一个测试点，名称为'登录验证'，优先级为高。",
            schema=schema,
            metadata={"step_name": "integration_test"},
        )
        assert resp.content
        assert resp.parsed is not None
        assert "name" in resp.parsed
        assert "priority" in resp.parsed

    def test_with_temperature(self, openai_client):
        """自定义 temperature"""
        resp = openai_client.complete(
            "说一个数字",
            temperature=0.0,
            max_tokens=10,
            metadata={"step_name": "integration_test"},
        )
        assert resp.content

    def test_call_log_recorded(self, openai_client):
        """验证调用日志被记录（无 DB 时仅验证不报错）"""
        # OpenAIClient 内部会调用 record_call，db=None 时不写入
        resp = openai_client.complete(
            "hello",
            metadata={"step_name": "integration_test"},
        )
        assert resp.content

    def test_error_handling_invalid_model(self):
        """错误模型名应抛出 AIServiceError"""
        from app.utils.ai_client_core import AIServiceError

        client = OpenAIClient(model="nonexistent-model-xyz")
        with pytest.raises(AIServiceError):
            client.complete("test", max_tokens=5)
