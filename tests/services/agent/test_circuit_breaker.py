"""CircuitBreaker 单元测试。

覆盖：
    - closed/open/half_open 状态机转换
    - allow/record_success/record_failure 行为
    - recovery_seconds 超时转 half_open
    - half_open 单次试探限制
    - Redis 模式状态持久化与异常降级
    - 自定义 threshold/recovery_seconds

被测：app/services/agent/circuit_breaker.py
"""
from unittest.mock import MagicMock, patch

import fakeredis

from app.core.config import settings
from app.services.agent.circuit_breaker import CircuitBreaker


def _make_fake_time(start: float = 1000.0):
    """创建可控的 fake time，返回 (fake_func, advance_func)。

    fake_func 返回当前时间戳；advance_func 推进时间。
    """
    current = [start]

    def fake_func() -> float:
        return current[0]

    def advance_func(seconds: float) -> None:
        current[0] += seconds

    return fake_func, advance_func


class TestClosedState:
    """closed 状态行为。"""

    async def test_initial_state_closed_allow_returns_true(self):
        """初始状态 closed → allow 返回 True。"""
        cb = CircuitBreaker(redis_client=None, threshold=3, recovery_seconds=100)
        assert await cb.allow("agent") is True

    async def test_closed_record_success_resets_failures(self):
        """closed 状态 record_success → 仍为 closed，失败计数归零。"""
        cb = CircuitBreaker(redis_client=None, threshold=3, recovery_seconds=100)
        await cb.record_failure("agent")  # failures=1
        await cb.record_success("agent")  # failures 归零
        assert await cb.allow("agent") is True
        # failures 已归零，2 次 failure 不会转 open
        await cb.record_failure("agent")
        await cb.record_failure("agent")
        assert await cb.allow("agent") is True

    async def test_closed_record_failure_below_threshold_stays_closed(self):
        """closed 状态 record_failure 未达阈值 → 仍为 closed。"""
        cb = CircuitBreaker(redis_client=None, threshold=3, recovery_seconds=100)
        await cb.record_failure("agent")
        await cb.record_failure("agent")
        assert await cb.allow("agent") is True

    async def test_closed_record_failure_reaches_threshold_transitions_open(self):
        """closed 状态 record_failure 达阈值 → 转 open。"""
        cb = CircuitBreaker(redis_client=None, threshold=3, recovery_seconds=100)
        await cb.record_failure("agent")
        await cb.record_failure("agent")
        await cb.record_failure("agent")
        # open 状态 allow=False（未超 recovery）
        assert await cb.allow("agent") is False


class TestOpenState:
    """open 状态行为。"""

    async def test_open_allow_before_recovery_returns_false(self):
        """open 状态 allow 未超 recovery_seconds → 返回 False。"""
        cb = CircuitBreaker(redis_client=None, threshold=2, recovery_seconds=100)
        await cb.record_failure("agent")
        await cb.record_failure("agent")  # open
        assert await cb.allow("agent") is False

    async def test_open_allow_after_recovery_transitions_half_open(self):
        """open 状态 allow 超过 recovery_seconds → 转 half_open，返回 True。"""
        fake_time, advance = _make_fake_time()
        cb = CircuitBreaker(redis_client=None, threshold=2, recovery_seconds=100)
        with patch("app.services.agent.circuit_breaker.time.time", side_effect=fake_time):
            await cb.record_failure("agent")
            await cb.record_failure("agent")  # open, opened_at=1000.0
            advance(50)
            assert await cb.allow("agent") is False  # 未超 recovery
            advance(60)  # 累计 +110，超 recovery
            assert await cb.allow("agent") is True  # half_open 试探


class TestHalfOpenState:
    """half_open 状态行为。"""

    async def test_half_open_record_success_transitions_closed(self):
        """half_open 状态 record_success → 转 closed。"""
        fake_time, advance = _make_fake_time()
        cb = CircuitBreaker(redis_client=None, threshold=2, recovery_seconds=100)
        with patch("app.services.agent.circuit_breaker.time.time", side_effect=fake_time):
            await cb.record_failure("agent")
            await cb.record_failure("agent")  # open
            advance(200)
            assert await cb.allow("agent") is True  # half_open
            await cb.record_success("agent")  # -> closed
        assert await cb.allow("agent") is True  # closed

    async def test_half_open_record_failure_transitions_open(self):
        """half_open 状态 record_failure → 转 open 重置计时。"""
        fake_time, advance = _make_fake_time()
        cb = CircuitBreaker(redis_client=None, threshold=2, recovery_seconds=100)
        with patch("app.services.agent.circuit_breaker.time.time", side_effect=fake_time):
            await cb.record_failure("agent")
            await cb.record_failure("agent")  # open, opened_at=1000
            advance(200)  # 1200
            assert await cb.allow("agent") is True  # half_open
            advance(50)  # 1250
            await cb.record_failure("agent")  # -> open, opened_at=1250
            advance(50)  # 1300，未超新 recovery
            assert await cb.allow("agent") is False  # 仍 open

    async def test_half_open_allows_only_one_probe(self):
        """half_open 状态仅允许 1 次试探（第二次 allow 返回 False）。"""
        fake_time, advance = _make_fake_time()
        cb = CircuitBreaker(redis_client=None, threshold=2, recovery_seconds=100)
        with patch("app.services.agent.circuit_breaker.time.time", side_effect=fake_time):
            await cb.record_failure("agent")
            await cb.record_failure("agent")  # open
            advance(200)
            assert await cb.allow("agent") is True  # half_open，probe 已占用
            assert await cb.allow("agent") is False  # 第二次试探被拒


class TestRedisMode:
    """Redis 模式。"""

    async def test_redis_state_persistence(self):
        """Redis 模式状态恢复：重新构造 CircuitBreaker，状态保持。"""
        redis_client = fakeredis.FakeRedis(decode_responses=True)
        try:
            cb1 = CircuitBreaker(redis_client=redis_client, threshold=2, recovery_seconds=100)
            await cb1.record_failure("agent")
            await cb1.record_failure("agent")  # open
            # 重新构造 cb2，共享同一 Redis，状态应保持
            cb2 = CircuitBreaker(redis_client=redis_client, threshold=2, recovery_seconds=100)
            assert await cb2.allow("agent") is False  # 仍 open
        finally:
            redis_client.flushdb()
            redis_client.close()

    async def test_redis_exception_fallback_to_memory(self):
        """Redis 异常降级内存模式。"""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("redis down")
        mock_redis.set.side_effect = Exception("redis down")
        mock_redis.incr.side_effect = Exception("redis down")
        mock_redis.delete.side_effect = Exception("redis down")
        cb = CircuitBreaker(redis_client=mock_redis, threshold=2, recovery_seconds=100)
        await cb.record_failure("agent")
        await cb.record_failure("agent")  # 内存中转 open
        assert await cb.allow("agent") is False  # 内存 open

    def test_try_redis_exception_returns_none(self):
        """_try_redis 异常捕获且降级内存：返回 None。"""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("boom")
        cb = CircuitBreaker(redis_client=mock_redis, threshold=2, recovery_seconds=100)
        result = cb._try_redis("测试", lambda: mock_redis.get("key"))
        assert result is None


class TestFullCycleAndConfig:
    """完整状态机循环与配置。"""

    async def test_memory_full_state_machine_cycle(self):
        """内存模式完整状态机循环：closed→open→half_open→closed。"""
        fake_time, advance = _make_fake_time()
        cb = CircuitBreaker(redis_client=None, threshold=2, recovery_seconds=100)
        with patch("app.services.agent.circuit_breaker.time.time", side_effect=fake_time):
            # closed -> open
            await cb.record_failure("agent")
            await cb.record_failure("agent")
            assert await cb.allow("agent") is False  # open
            # open -> half_open
            advance(200)
            assert await cb.allow("agent") is True  # half_open
            # half_open -> closed
            await cb.record_success("agent")
        assert await cb.allow("agent") is True  # closed

    def test_custom_threshold_and_recovery_override_defaults(self):
        """自定义 threshold / recovery_seconds 覆盖默认值。"""
        cb = CircuitBreaker(redis_client=None, threshold=42, recovery_seconds=999)
        assert cb._threshold == 42
        assert cb._recovery_seconds == 999
        # 默认值断言（确认覆盖了不同的值）
        assert settings.AI_AGENT_CIRCUIT_BREAKER_THRESHOLD == 5
        assert settings.AI_AGENT_CIRCUIT_BREAKER_RECOVERY_SECONDS == 300
