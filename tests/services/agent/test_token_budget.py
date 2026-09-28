"""AgentTokenBudgetGuard + BaseTokenBudgetGuard 单元测试。

覆盖 check_single_call / is_daily_budget_exhausted / consume / _get_consumed
及 Redis key namespace 隔离、TTL、内存降级等分支。

Redis 测试使用 fakeredis（项目规则允许），避免依赖真实 Redis 服务。

被测：
    - app/services/agent/token_budget.py（AgentTokenBudgetGuard）
    - app/services/common/token_budget.py（BaseTokenBudgetGuard）
"""
from datetime import datetime
from unittest.mock import MagicMock

import fakeredis
import pytest

from app.core.config import settings
from app.services.agent.token_budget import AgentTokenBudgetGuard
from app.services.common.token_budget import BaseTokenBudgetGuard

_DEFAULT_TTL_SECONDS: int = 25 * 3600


class _SelfHealGuardStub(BaseTokenBudgetGuard):
    """self_heal 场景的 stub，用于验证 namespace 隔离。"""

    def __init__(self, redis_client) -> None:
        super().__init__(redis_client=redis_client, namespace="self_heal:token:")

    def check_single_call(self, token_estimate: int) -> bool:
        return False

    def is_daily_budget_exhausted(self) -> bool:
        return False


@pytest.fixture
def fake_redis():
    """每次测试创建独立的 fakeredis 客户端，自动隔离 key 空间。"""
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()


class TestCheckSingleCall:
    """check_single_call 单次 Token 预算校验。"""

    def test_over_limit_returns_true(self, fake_redis):
        """超限 → True。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        assert guard.check_single_call(settings.AI_AGENT_TOKEN_LIMIT + 1) is True

    def test_within_limit_returns_false(self, fake_redis):
        """未超限 → False。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        assert guard.check_single_call(settings.AI_AGENT_TOKEN_LIMIT) is False


class TestIsDailyBudgetExhausted:
    """is_daily_budget_exhausted 日预算耗尽判断。"""

    def test_not_exhausted(self, fake_redis):
        """未达预算 → False。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        guard.consume(1000)
        assert guard.is_daily_budget_exhausted() is False

    def test_exhausted(self, fake_redis):
        """达预算 → True。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        guard.consume(settings.AI_AGENT_DAILY_TOKEN_BUDGET)
        assert guard.is_daily_budget_exhausted() is True


class TestConsume:
    """consume Redis 累计与降级。"""

    def test_consume_accumulates_to_redis(self, fake_redis):
        """累计到 Redis。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        guard.consume(500)
        guard.consume(300)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"agent:token:test_generation:1:{day}"
        assert int(fake_redis.get(counter_key)) == 800

    def test_consume_redis_exception_falls_back_to_memory(self):
        """Redis 异常 → 降级内存计数。"""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("Redis connection lost")
        guard = AgentTokenBudgetGuard(
            redis_client=mock_redis, agent_type="test_generation", project_id=1,
        )
        guard.consume(500)
        assert guard._memory_counter == 500

    def test_get_consumed_redis_exception_returns_memory(self):
        """_get_consumed Redis 异常 → 返回内存计数。"""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis read failed")
        guard = AgentTokenBudgetGuard(
            redis_client=mock_redis, agent_type="test_generation", project_id=1,
        )
        guard._memory_counter = 1000
        assert guard._get_consumed() == 1000


class TestRedisKeyNamespace:
    """Redis key namespace 隔离与拼接。"""

    def test_namespace_isolation_between_agent_and_self_heal(self, fake_redis):
        """agent:token:{type}:{pid}: vs self_heal:token: 隔离。"""
        agent_guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        self_heal_guard = _SelfHealGuardStub(redis_client=fake_redis)
        agent_guard.consume(1000)
        self_heal_guard.consume(2000)
        assert agent_guard._get_consumed() == 1000
        assert self_heal_guard._get_consumed() == 2000

    def test_redis_key_includes_date_yyyymmdd(self, fake_redis):
        """Redis key 按日期拼接（YYYYMMDD）。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        guard.consume(100)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = guard._build_counter_key(day)
        assert day in counter_key
        assert fake_redis.get(counter_key) is not None

    def test_ttl_set_correctly_25h(self, fake_redis):
        """TTL 设置正确（25h）。"""
        guard = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        guard.consume(100)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = guard._build_counter_key(day)
        ttl = fake_redis.ttl(counter_key)
        assert _DEFAULT_TTL_SECONDS - 10 <= ttl <= _DEFAULT_TTL_SECONDS

    def test_namespace_isolated_by_agent_type_and_project_id(self, fake_redis):
        """按 agent_type+project_id 隔离 namespace。"""
        guard_a = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="test_generation", project_id=1,
        )
        guard_b = AgentTokenBudgetGuard(
            redis_client=fake_redis, agent_type="failure_analysis", project_id=2,
        )
        guard_a.consume(1000)
        guard_b.consume(2000)
        assert guard_a._get_consumed() == 1000
        assert guard_b._get_consumed() == 2000
