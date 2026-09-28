"""TokenBudgetGuard 单元测试。

覆盖：
    - check_single_call：token_estimate > limit → True
    - check_single_call：token_estimate ≤ limit → False
    - consume：Redis 可用时 INCRBY 累计（fakeredis）
    - consume：Redis None 时降级内存计数
    - is_daily_budget_exhausted：累计超 500000 → True
    - is_daily_budget_exhausted：未超 → False
    - Redis 异常降级：consume 不抛异常，走内存
    - 边界：amount=0, 负数

被测：app/services/self_healing/token_budget.py（TokenBudgetGuard）
Redis 测试使用 fakeredis（项目规则允许），避免依赖真实 Redis 服务。
"""
from datetime import datetime
from unittest.mock import patch, MagicMock

import fakeredis
import pytest

from app.core.config import settings
from app.services.self_healing.token_budget import (
    TokenBudgetGuard,
    _TOKEN_KEY_PREFIX,
    _TTL_SECONDS,
)


@pytest.fixture
def fake_redis_client():
    """每次测试创建独立的 fakeredis 客户端，自动隔离 key 空间。"""
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()


class TestCheckSingleCall:
    """check_single_call 单次 Token 预算校验。"""

    def setup_method(self) -> None:
        self.guard = TokenBudgetGuard(redis_client=None)

    def test_over_limit_returns_true(self):
        """token_estimate > AI_SELF_HEALING_TOKEN_LIMIT(2000) → True（超限）。"""
        assert self.guard.check_single_call(3000) is True

    def test_within_limit_returns_false(self):
        """token_estimate ≤ limit → False（在限额内）。"""
        assert self.guard.check_single_call(1000) is False

    def test_exactly_at_limit_returns_false(self):
        """等于 limit 时不超限（> 而非 >=）。"""
        assert self.guard.check_single_call(settings.AI_SELF_HEALING_TOKEN_LIMIT) is False

    def test_zero_tokens_returns_false(self):
        """token_estimate=0 → False。"""
        assert self.guard.check_single_call(0) is False

    def test_large_value_returns_true(self):
        """极大值 → True。"""
        assert self.guard.check_single_call(1_000_000) is True


class TestConsumeWithRedis:
    """consume 在 Redis 可用时的累计行为。"""

    def test_consume_increments_redis_counter(self, fake_redis_client):
        """Redis 可用时 INCRBY 累计计数。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(500)
        guard.consume(300)

        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"{_TOKEN_KEY_PREFIX}{day}"
        # 累计应为 800
        assert int(fake_redis_client.get(counter_key)) == 800

    def test_consume_sets_ttl_on_first_write(self, fake_redis_client):
        """首次写入时设置 TTL（25h），后续不刷新。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(100)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"{_TOKEN_KEY_PREFIX}{day}"
        ttl = fake_redis_client.ttl(counter_key)
        # TTL 应为 25h（允许 5 秒误差）
        assert _TTL_SECONDS - 10 <= ttl <= _TTL_SECONDS

    def test_consume_does_not_refresh_ttl_on_subsequent_writes(
        self, fake_redis_client
    ):
        """后续写入不刷新 TTL（避免 key 永生）。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(100)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"{_TOKEN_KEY_PREFIX}{day}"
        ttl_after_first = fake_redis_client.ttl(counter_key)

        # 等待一小段时间后再 consume（TTL 应略减）
        import time
        time.sleep(1)
        guard.consume(200)
        ttl_after_second = fake_redis_client.ttl(counter_key)

        # TTL 应该减小（约 1 秒），不应被刷新回 25h
        assert ttl_after_second < ttl_after_first
        assert ttl_after_second < _TTL_SECONDS

    def test_consume_zero_amount(self, fake_redis_client):
        """amount=0 应正常处理（INCRBY 0 不报错）。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(0)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"{_TOKEN_KEY_PREFIX}{day}"
        assert int(fake_redis_client.get(counter_key)) == 0

    def test_consume_negative_amount_increments_zero(self, fake_redis_client):
        """amount 为负数时 INCRBY 会减少计数（Redis 行为）。

        业务层应避免传入负数，但 TokenBudgetGuard 不做防御（INCRBY 负数合法）。
        """
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(100)
        guard.consume(-30)
        day = datetime.now().strftime("%Y%m%d")
        counter_key = f"{_TOKEN_KEY_PREFIX}{day}"
        # INCRBY -30 会减少计数
        assert int(fake_redis_client.get(counter_key)) == 70


class TestConsumeMemoryFallback:
    """consume 在 Redis 不可用（None）时的内存降级。"""

    def test_consume_memory_counter_when_redis_none(self):
        """Redis=None 时降级内存计数。"""
        guard = TokenBudgetGuard(redis_client=None)
        guard.consume(500)
        guard.consume(300)
        assert guard._memory_counter == 800

    def test_consume_memory_counter_accumulates(self):
        """内存计数器持续累计。"""
        guard = TokenBudgetGuard(redis_client=None)
        for _ in range(5):
            guard.consume(100)
        assert guard._memory_counter == 500

    def test_consume_zero_amount_memory(self):
        """amount=0 内存计数器不变。"""
        guard = TokenBudgetGuard(redis_client=None)
        guard.consume(0)
        assert guard._memory_counter == 0


class TestConsumeRedisExceptionFallback:
    """consume 在 Redis 异常时降级内存计数。"""

    def test_consume_redis_exception_falls_back_to_memory(self):
        """Redis 抛异常时降级内存，不抛出。"""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("Redis connection lost")
        guard = TokenBudgetGuard(redis_client=mock_redis)

        # 不应抛异常
        guard.consume(500)
        assert guard._memory_counter == 500

    def test_consume_redis_pipeline_execute_exception_falls_back(self):
        """Redis pipeline.execute 抛异常时降级内存。"""
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.incrby = MagicMock()
        mock_pipe.set = MagicMock()
        mock_pipe.execute.side_effect = Exception("pipeline failed")
        mock_redis.pipeline.return_value = mock_pipe
        guard = TokenBudgetGuard(redis_client=mock_redis)

        guard.consume(200)
        assert guard._memory_counter == 200


class TestIsDailyBudgetExhausted:
    """is_daily_budget_exhausted 日预算耗尽判断。"""

    def test_exhausted_when_over_budget_with_redis(self, fake_redis_client):
        """Redis 累计超 500000 → True。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        # 一次性消耗超预算
        guard.consume(settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET + 1)
        assert guard.is_daily_budget_exhausted() is True

    def test_not_exhausted_when_under_budget_with_redis(self, fake_redis_client):
        """Redis 累计未超 500000 → False。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(1000)
        assert guard.is_daily_budget_exhausted() is False

    def test_exhausted_when_exactly_at_budget(self, fake_redis_client):
        """累计等于预算时视为耗尽（>= 判断）。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        guard.consume(settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET)
        assert guard.is_daily_budget_exhausted() is True

    def test_exhausted_with_memory_counter(self):
        """内存计数超预算 → True。"""
        guard = TokenBudgetGuard(redis_client=None)
        guard._memory_counter = settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET + 100
        assert guard.is_daily_budget_exhausted() is True

    def test_not_exhausted_with_memory_counter(self):
        """内存计数未超预算 → False。"""
        guard = TokenBudgetGuard(redis_client=None)
        guard._memory_counter = 1000
        assert guard.is_daily_budget_exhausted() is False

    def test_exhausted_redis_exception_falls_back_to_memory(self):
        """Redis 读取异常时降级内存计数。"""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis read failed")
        guard = TokenBudgetGuard(redis_client=mock_redis)
        guard._memory_counter = settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET + 1
        assert guard.is_daily_budget_exhausted() is True

    def test_exhausted_redis_returns_none(self):
        """Redis 返回 None（无累计）→ False。"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        guard = TokenBudgetGuard(redis_client=mock_redis)
        assert guard.is_daily_budget_exhausted() is False

    def test_exhausted_redis_returns_empty_string(self):
        """Redis 返回空字符串 → 视为 0，未耗尽。"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = ""
        guard = TokenBudgetGuard(redis_client=mock_redis)
        assert guard.is_daily_budget_exhausted() is False


class TestEndToEndWithRedis:
    """端到端：consume → is_daily_budget_exhausted 完整流程。"""

    def test_end_to_end_accumulation_and_exhaustion(self, fake_redis_client):
        """多次 consume 累计，最终触发预算耗尽。"""
        guard = TokenBudgetGuard(redis_client=fake_redis_client)
        budget = settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET

        # 分批消耗，最后一笔触发耗尽
        guard.consume(budget // 2)
        assert guard.is_daily_budget_exhausted() is False

        guard.consume(budget // 2)
        # 等于预算时视为耗尽
        assert guard.is_daily_budget_exhausted() is True

    def test_end_to_end_memory_fallback(self):
        """Redis=None 端到端流程。"""
        guard = TokenBudgetGuard(redis_client=None)
        budget = settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET

        guard.consume(budget - 1)
        assert guard.is_daily_budget_exhausted() is False

        guard.consume(1)
        assert guard.is_daily_budget_exhausted() is True
