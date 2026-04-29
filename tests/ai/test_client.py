"""
M1-T08 AI Client 抽象层单元测试

覆盖范围：
1. AIResponse / TokenUsage 数据类
2. AIClient Protocol 兼容性检查
3. MockAIClient：预设响应、调用计数、零成本
4. FallbackAIClient：主备切换、degraded 标记、失败计数
5. AICallLog 模型 + record_call + check_budget + get_run_cost
"""
import pytest

from app.ai.client import AIClient, AIResponse, TokenUsage
from app.ai.mock_client import MockAIClient
from app.ai.fallback_client import FallbackAIClient
from app.ai.call_log import AICallLog, record_call, check_budget, get_run_cost
from app.models.pipeline import PipelineRun
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.user import User
from app.models.enums import PipelineRunStatus


# ==================== Fixtures ====================

@pytest.fixture
def test_user(db):
    user = User(username="ai_test_user", email="ai_test@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="AI测试项目", user_id=test_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    return project


@pytest.fixture
def test_iteration(db, test_project):
    it = Iteration(project_id=test_project.id, name="Sprint AI", version="v1.0")
    db.add(it)
    db.flush()
    db.refresh(it)
    return it


@pytest.fixture
def test_run(db, test_iteration):
    run = PipelineRun(
        iteration_id=test_iteration.id,
        input_hash="test_hash",
        pipeline_version="1.0",
        status=PipelineRunStatus.RUNNING.value,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


# ==================== 数据类 ====================

class TestDataClasses:
    """AIResponse / TokenUsage 数据类测试"""

    def test_token_usage_defaults(self):
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_cost_usd == 0.0

    def test_token_usage_custom(self):
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_cost_usd=0.015)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_cost_usd == 0.015

    def test_ai_response_defaults(self):
        resp = AIResponse()
        assert resp.content == ""
        assert resp.parsed is None
        assert resp.usage.prompt_tokens == 0
        assert resp.model_version == ""
        assert resp.latency_ms == 0
        assert resp.degraded is False

    def test_ai_response_custom(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20)
        resp = AIResponse(
            content="hello",
            parsed={"key": "value"},
            usage=usage,
            model_version="test-model",
            latency_ms=100,
            degraded=True,
        )
        assert resp.content == "hello"
        assert resp.parsed == {"key": "value"}
        assert resp.degraded is True


# ==================== AIClient Protocol ====================

class TestAIClientProtocol:
    """AIClient Protocol 兼容性测试"""

    def test_mock_is_aiclient(self):
        mock = MockAIClient()
        assert isinstance(mock, AIClient)

    def test_custom_impl_is_aiclient(self):
        class MyClient:
            def complete(self, prompt, *, system=None, schema=None,
                         temperature=None, max_tokens=None, metadata=None):
                return AIResponse(content="ok")
        assert isinstance(MyClient(), AIClient)

    def test_non_impl_not_aiclient(self):
        class NotAClient:
            pass
        assert not isinstance(NotAClient(), AIClient)


# ==================== MockAIClient ====================

class TestMockAIClient:
    """MockAIClient 测试"""

    def test_default_response(self):
        mock = MockAIClient()
        resp = mock.complete("test prompt")
        assert resp.parsed == {"result": "mock"}
        assert resp.usage.total_cost_usd == 0.0
        assert resp.model_version == "mock-model"
        assert resp.degraded is False

    def test_custom_default_response(self):
        mock = MockAIClient(default_response={"custom": "data"})
        resp = mock.complete("test")
        assert resp.parsed == {"custom": "data"}

    def test_set_response_by_step(self):
        mock = MockAIClient()
        mock.set_response("signal_gatherer", {"signals": [1, 2, 3]})
        mock.set_response("test_point_gen", {"points": ["a", "b"]})

        resp1 = mock.complete("prompt", metadata={"step_name": "signal_gatherer"})
        assert resp1.parsed == {"signals": [1, 2, 3]}

        resp2 = mock.complete("prompt", metadata={"step_name": "test_point_gen"})
        assert resp2.parsed == {"points": ["a", "b"]}

    def test_string_response(self):
        mock = MockAIClient(default_response="plain text response")
        resp = mock.complete("test")
        assert resp.content == "plain text response"
        assert resp.parsed is None

    def test_call_count_and_history(self):
        mock = MockAIClient()
        mock.complete("prompt1")
        mock.complete("prompt2")
        assert mock.call_count == 2
        assert mock.call_history[0]["prompt"] == "prompt1"
        assert mock.call_history[1]["prompt"] == "prompt2"

    def test_zero_cost(self):
        mock = MockAIClient()
        resp = mock.complete("test")
        assert resp.usage.prompt_tokens == 0
        assert resp.usage.completion_tokens == 0
        assert resp.usage.total_cost_usd == 0.0

    def test_reset(self):
        mock = MockAIClient()
        mock.set_response("step", {"data": 1})
        mock.complete("test")
        mock.reset()
        assert mock.call_count == 0
        resp = mock.complete("test", metadata={"step_name": "step"})
        assert resp.parsed == {"result": "mock"}

    def test_metadata_passed(self):
        mock = MockAIClient()
        mock.complete("test", metadata={"step_name": "s1", "run_id": 42})
        assert mock.call_history[0]["metadata"]["step_name"] == "s1"
        assert mock.call_history[0]["metadata"]["run_id"] == 42


# ==================== FallbackAIClient ====================

class TestFallbackAIClient:
    """FallbackAIClient 主备切换测试"""

    def test_primary_success(self):
        mock_primary = MockAIClient(default_response={"from": "primary"})
        mock_fallback = MockAIClient(default_response={"from": "fallback"})
        client = FallbackAIClient(mock_primary, mock_fallback)

        resp = client.complete("test")
        assert resp.parsed == {"from": "primary"}
        assert resp.degraded is False
        assert client.switched is False

    def test_primary_fails_once_raises(self):
        class FailingClient:
            def complete(self, prompt, **kwargs):
                raise RuntimeError("primary down")
        mock_fallback = MockAIClient(default_response={"from": "fallback"})
        client = FallbackAIClient(FailingClient(), mock_fallback, max_failures=3)

        with pytest.raises(RuntimeError, match="primary down"):
            client.complete("test")
        assert client.failure_count == 1
        assert client.switched is False

    def test_primary_fails_3_times_switches(self):
        class FailingClient:
            def complete(self, prompt, **kwargs):
                raise RuntimeError("primary down")
        mock_fallback = MockAIClient(default_response={"from": "fallback"})
        client = FallbackAIClient(FailingClient(), mock_fallback, max_failures=3)

        for _ in range(2):
            with pytest.raises(RuntimeError):
                client.complete("test")

        resp = client.complete("test")
        assert resp.parsed == {"from": "fallback"}
        assert resp.degraded is True
        assert client.switched is True

    def test_switched_subsequent_calls_use_fallback(self):
        class FailingClient:
            def complete(self, prompt, **kwargs):
                raise RuntimeError("primary down")
        mock_fallback = MockAIClient(default_response={"from": "fallback"})
        client = FallbackAIClient(FailingClient(), mock_fallback, max_failures=1)

        resp = client.complete("test")
        assert resp.degraded is True

        resp2 = client.complete("test2")
        assert resp2.parsed == {"from": "fallback"}
        assert resp2.degraded is True
        assert mock_fallback.call_count == 2

    def test_primary_success_resets_failure_count(self):
        call_count = 0

        class SometimesFailingClient:
            def complete(self, prompt, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("transient error")
                return AIResponse(content="ok")
        mock_fallback = MockAIClient()
        client = FallbackAIClient(SometimesFailingClient(), mock_fallback, max_failures=3)

        with pytest.raises(RuntimeError):
            client.complete("test")
        assert client.failure_count == 1

        resp = client.complete("test")
        assert client.failure_count == 0
        assert client.switched is False

    def test_reset(self):
        class FailingClient:
            def complete(self, prompt, **kwargs):
                raise RuntimeError("down")
        mock_fallback = MockAIClient()
        client = FallbackAIClient(FailingClient(), mock_fallback, max_failures=1)

        resp = client.complete("test")
        assert client.switched is True

        client.reset()
        assert client.failure_count == 0
        assert client.switched is False

    def test_custom_max_failures(self):
        class FailingClient:
            def complete(self, prompt, **kwargs):
                raise RuntimeError("down")
        mock_fallback = MockAIClient()
        client = FallbackAIClient(FailingClient(), mock_fallback, max_failures=5)

        for _ in range(4):
            with pytest.raises(RuntimeError):
                client.complete("test")
        assert client.switched is False

        resp = client.complete("test")
        assert client.switched is True


# ==================== AICallLog ====================

class TestAICallLog:
    """AICallLog 模型 + record_call + check_budget 测试"""

    def test_record_call_success(self, db, test_run):
        log = record_call(
            db,
            model="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.015,
            latency_ms=500,
            step_name="signal_gatherer",
            run_id=test_run.id,
        )
        assert log.id is not None
        assert log.model == "deepseek-chat"
        assert log.prompt_tokens == 100
        assert log.completion_tokens == 50
        assert log.step_name == "signal_gatherer"
        assert log.run_id == test_run.id
        assert log.status == "success"

    def test_record_call_failure(self, db, test_run):
        log = record_call(
            db,
            model="deepseek-chat",
            latency_ms=3000,
            step_name="test_point_gen",
            run_id=test_run.id,
            status="failed",
            error_message="timeout after 30s",
        )
        assert log.status == "failed"
        assert log.error_message == "timeout after 30s"
        assert log.prompt_tokens == 0

    def test_record_call_no_db(self):
        log = record_call(
            model="mock",
            prompt_tokens=10,
            completion_tokens=5,
        )
        assert log.model == "mock"
        assert log.id is None

    def test_check_budget_within(self, db, test_run):
        record_call(db, model="deepseek-chat", prompt_tokens=100,
                    completion_tokens=50, run_id=test_run.id)
        assert check_budget(db, test_run.id) is True

    def test_check_budget_exceeded(self, db, test_run):
        for _ in range(5):
            record_call(db, model="deepseek-chat",
                        prompt_tokens=25000, completion_tokens=1000,
                        run_id=test_run.id)
        assert check_budget(db, test_run.id) is False

    def test_check_budget_ignores_failed(self, db, test_run):
        record_call(db, model="deepseek-chat", prompt_tokens=50000,
                    completion_tokens=50000, run_id=test_run.id, status="failed")
        assert check_budget(db, test_run.id) is True

    def test_get_run_cost(self, db, test_run):
        record_call(db, model="deepseek-chat", cost_usd=0.01, run_id=test_run.id)
        record_call(db, model="deepseek-chat", cost_usd=0.02, run_id=test_run.id)
        total = get_run_cost(db, test_run.id)
        assert abs(total - 0.03) < 0.001

    def test_get_run_cost_empty(self, db, test_run):
        total = get_run_cost(db, test_run.id)
        assert total == 0.0

    def test_ai_call_log_repr(self, db, test_run):
        log = record_call(db, model="test-model", run_id=test_run.id)
        repr_str = repr(log)
        assert "test-model" in repr_str
