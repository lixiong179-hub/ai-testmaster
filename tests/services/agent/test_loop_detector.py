"""LoopDetector 单元测试。

覆盖：
    - _build_signature 签名生成与顺序无关性
    - check 累积检测、窗口滑动、阈值触发
    - reset 清空窗口
    - Redis 模式 / 内存模式 / Redis 异常降级
    - threshold 默认值与自定义覆盖

被测：app/services/agent/loop_detector.py
"""
from unittest.mock import MagicMock

import fakeredis

from app.core.config import settings
from app.services.agent.loop_detector import LoopDetector


class TestBuildSignature:
    """_build_signature 签名构造。"""

    def test_build_signature_format(self):
        """签名格式为 tool_name:sorted_args_json。"""
        sig = LoopDetector._build_signature("search", {"query": "hello", "limit": 10})
        expected = 'search:{"limit": 10, "query": "hello"}'
        assert sig == expected

    def test_build_signature_order_independent(self):
        """字典顺序不影响签名：{"a":1,"b":2} 与 {"b":2,"a":1} 签名相同。"""
        sig1 = LoopDetector._build_signature("tool", {"a": 1, "b": 2})
        sig2 = LoopDetector._build_signature("tool", {"b": 2, "a": 1})
        assert sig1 == sig2


class TestCheckMemory:
    """check 内存模式（redis_client=None）。"""

    async def test_check_first_call_returns_false(self):
        """首次调用 check 返回 False。"""
        detector = LoopDetector(redis_client=None, threshold=3, window_size=10)
        sig = LoopDetector._build_signature("tool", {"a": 1})
        result = await detector.check(
            agent_type="default", session_id=1, tool_call_signature=sig
        )
        assert result is False

    async def test_check_accumulate_to_threshold_returns_true(self):
        """同签名累积达 threshold 返回 True。"""
        detector = LoopDetector(redis_client=None, threshold=3, window_size=10)
        sig = LoopDetector._build_signature("tool", {"a": 1})
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is True

    async def test_check_different_signatures_no_accumulation(self):
        """不同签名不累积：交替调用 a/b 不触发循环。"""
        detector = LoopDetector(redis_client=None, threshold=2, window_size=2)
        sig_a = LoopDetector._build_signature("tool", {"a": 1})
        sig_b = LoopDetector._build_signature("tool", {"b": 1})
        for _ in range(5):
            r_a = await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a)
            r_b = await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_b)
            assert r_a is False
            assert r_b is False

    async def test_check_window_size_effect(self):
        """window_size=3 时，第 4 次签名替换第 1 次。"""
        detector = LoopDetector(redis_client=None, threshold=3, window_size=3)
        sig_a = LoopDetector._build_signature("tool", {"a": 1})
        sig_b = LoopDetector._build_signature("tool", {"b": 1})
        sig_c = LoopDetector._build_signature("tool", {"c": 1})
        # 1,2,3: a,b,c 填满窗口 [a,b,c]
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_b) is False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_c) is False
        # 4: a -> 窗口滑动 [b,c,a]，count(a)=1，不触发
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is False
        # 5: a -> [c,a,a]，count=2，不触发
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is False
        # 6: a -> [a,a,a]，count=3，触发
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is True

    async def test_reset_clears_window(self):
        """reset 清空窗口后 check 返回 False。"""
        detector = LoopDetector(redis_client=None, threshold=2, window_size=10)
        sig = LoopDetector._build_signature("tool", {"a": 1})
        await detector.check(agent_type="default", session_id=1, tool_call_signature=sig)
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is True
        await detector.reset(agent_type="default", session_id=1)
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is False

    async def test_memory_mode_full_flow(self):
        """内存模式完整流程：累积、触发、reset 后重新累积。"""
        detector = LoopDetector(redis_client=None, threshold=3, window_size=5)
        sig_a = LoopDetector._build_signature("tool", {"a": 1})
        sig_b = LoopDetector._build_signature("tool", {"b": 1})
        # 不同签名交替不触发：[a] -> [a,b] -> [a,b,a]，count(a)=2 < 3
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_b) is False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is False
        # 同签名累积触发：[a,b,a,a]，count(a)=3 >= 3
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is True
        # reset 后窗口清空，重新开始
        await detector.reset(agent_type="default", session_id=1)
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig_a) is False


class TestCheckRedis:
    """check Redis 模式。"""

    async def test_redis_mode_works(self):
        """Redis 模式正常工作。"""
        redis_client = fakeredis.FakeRedis(decode_responses=True)
        try:
            detector = LoopDetector(redis_client=redis_client, threshold=3, window_size=10)
            sig = LoopDetector._build_signature("tool", {"a": 1})
            assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is False
            assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is False
            assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is True
        finally:
            redis_client.flushdb()
            redis_client.close()

    async def test_redis_exception_fallback_to_memory(self):
        """Redis 异常时降级内存模式。"""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("redis down")
        detector = LoopDetector(redis_client=mock_redis, threshold=2, window_size=10)
        sig = LoopDetector._build_signature("tool", {"a": 1})
        # 第一次：Redis 异常 -> 降级内存，count=1，False
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is False
        # 第二次：再次降级内存，count=2，True
        assert await detector.check(agent_type="default", session_id=1, tool_call_signature=sig) is True


class TestThresholdConfig:
    """threshold 配置读取。"""

    def test_default_threshold_from_settings(self):
        """threshold 默认从 settings.AI_AGENT_LOOP_DETECTION_THRESHOLD 读取。"""
        detector = LoopDetector(redis_client=None)
        assert detector._threshold == settings.AI_AGENT_LOOP_DETECTION_THRESHOLD

    def test_custom_threshold_overrides_default(self):
        """自定义 threshold 覆盖默认值。"""
        detector = LoopDetector(redis_client=None, threshold=99)
        assert detector._threshold == 99
