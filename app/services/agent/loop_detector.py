"""Agent 循环检测器。

AgentRuntime 多轮 function calling 中，LLM 可能陷入"重复调用相同工具+相同参数"
的死循环。本模块基于"最近 N 次工具调用签名重复次数"检测此类死循环，触发后
由 AgentRuntime 抛 AgentLoopDetected 终止会话。

检测原理：
    1. 调用方在每次工具调用前传入 tool_call_signature（建议由 _build_signature 生成）
    2. 检测器维护最近 window_size 次签名的滑动窗口
    3. 统计当前签名在窗口内的出现次数，>= threshold 返回 True（检测到循环）
    4. 检测到循环不抛异常，由调用方决定如何处理

存储：Redis list key=`agent:loop:{agent_type}:{session_id}` 用 LPUSH+LTRIM 维护窗口；
      Redis 不可用或异常时降级为 deque(maxlen=window_size)。
"""
from __future__ import annotations

import json
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from loguru import logger

from app.core.config import settings

# 循环检测窗口 Redis key 模板，{agent_type}/{session_id} 在调用时填充
_LOOP_KEY_TEMPLATE = "agent:loop:{agent_type}:{session_id}"


class LoopDetector:
    """Agent 工具调用循环检测器。

    Attributes:
        _redis: 同步 redis.Redis 实例（decode_responses=True）；None 时走内存降级。
        _threshold: 触发循环的重复次数阈值，默认 settings.AI_AGENT_LOOP_DETECTION_THRESHOLD。
        _window_size: 滑动窗口大小，默认 10。
        _memory_windows: Redis 不可用时的进程内窗口，按 key 隔离。
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        *,
        threshold: Optional[int] = None,
        window_size: int = 10,
    ) -> None:
        """注入 Redis 客户端与检测参数。

        Args:
            redis_client: 同步 redis.Redis 实例；为 None 时走内存降级。
            threshold: 循环触发阈值；None 时从 settings.AI_AGENT_LOOP_DETECTION_THRESHOLD 读取。
            window_size: 滑动窗口大小，最近 N 次签名参与统计。
        """
        self._redis = redis_client
        self._threshold = threshold if threshold is not None else settings.AI_AGENT_LOOP_DETECTION_THRESHOLD
        self._window_size = window_size
        self._memory_windows: Dict[str, Deque[str]] = {}

    @staticmethod
    def _build_signature(tool_name: str, args: Dict[str, Any]) -> str:
        """构造工具调用签名：tool_name:sorted_args_json。sorted_keys 保证字典顺序无关。"""
        args_json = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        return f"{tool_name}:{args_json}"

    def _build_key(self, agent_type: str, session_id: Optional[int]) -> str:
        """构造 Redis key，session_id 为 None 时使用 'global' 占位。"""
        sid = session_id if session_id is not None else "global"
        return _LOOP_KEY_TEMPLATE.format(agent_type=agent_type, session_id=sid)

    async def check(
        self,
        *,
        agent_type: str,
        session_id: Optional[int],
        tool_call_signature: str,
    ) -> bool:
        """检测当前签名是否触发循环。

        流程：写入窗口（LPUSH+LTRIM / deque.append）→ 读取窗口 → 统计签名
        出现次数 >= threshold 返回 True。Redis 异常时降级内存模式。

        Args:
            agent_type: Agent 类型标识。
            session_id: 会话 ID，None 时按 'global' 聚合。
            tool_call_signature: 工具调用签名，建议由 _build_signature 生成。

        Returns:
            bool: True 表示检测到循环，调用方应抛 AgentLoopDetected。
        """
        key = self._build_key(agent_type, session_id)
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.lpush(key, tool_call_signature)
                pipe.ltrim(key, 0, self._window_size - 1)
                pipe.lrange(key, 0, self._window_size - 1)
                window: List[str] = pipe.execute()[2] or []
                count = sum(1 for sig in window if sig == tool_call_signature)
                return count >= self._threshold
            except Exception as e:
                logger.warning(f"Redis 循环检测失败，降级内存模式: {e}")
        window_deque = self._memory_windows.setdefault(key, deque(maxlen=self._window_size))
        window_deque.append(tool_call_signature)
        return window_deque.count(tool_call_signature) >= self._threshold

    async def reset(self, *, agent_type: str, session_id: Optional[int]) -> None:
        """清空指定会话的循环检测窗口，用于会话结束或循环熔断后重置。"""
        key = self._build_key(agent_type, session_id)
        if self._redis is not None:
            try:
                self._redis.delete(key)
                return
            except Exception as e:
                logger.warning(f"Redis 重置循环窗口失败，降级内存模式: {e}")
        self._memory_windows.pop(key, None)


__all__ = ["LoopDetector"]
