"""Agent 熔断器（状态机 closed/open/half_open）。

当 Agent 连续失败超过阈值时熔断器转为 open 拒绝新会话，避免故障级联。
open 持续 recovery_seconds 后转 half_open 允许 1 次试探，试探成功转 closed
恢复正常，试探失败回退 open。open 状态 record_failure/record_success 忽略。

状态机转换：
    closed ──record_failure≥threshold──> open（记录 opened_at）
    open ──allow 且 elapsed≥recovery──> half_open（acquire_probe）
    half_open ──record_success──> closed；half_open ──record_failure──> open

存储：Redis state/failures/opened_at/probe 四 key 按 agent_type 隔离；异常降级 dict。
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, TypeVar

from loguru import logger

from app.core.config import settings

# 熔断器 Redis key 前缀，{agent_type} 在调用时填充，后缀为 state/failures/opened_at/probe
_CB_KEY_PREFIX = "agent:cb:{agent_type}:"
_CLOSED = "closed"
_OPEN = "open"
_HALF_OPEN = "half_open"
T = TypeVar("T")


class CircuitBreaker:
    """Agent 熔断器状态机（closed/open/half_open）。

    Attributes:
        _redis: 同步 redis.Redis 实例；None 时走内存降级。
        _threshold: 失败转 open 阈值，默认 settings.AI_AGENT_CIRCUIT_BREAKER_THRESHOLD。
        _recovery_seconds: open 持续秒数，默认 settings.AI_AGENT_CIRCUIT_BREAKER_RECOVERY_SECONDS。
        _memory_state: Redis 不可用时的进程内状态，按 agent_type 隔离。
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        *,
        threshold: Optional[int] = None,
        recovery_seconds: Optional[int] = None,
    ) -> None:
        """注入 Redis 与熔断参数；threshold/recovery_seconds 为 None 时从 settings 读取。"""
        self._redis = redis_client
        self._threshold = threshold if threshold is not None else settings.AI_AGENT_CIRCUIT_BREAKER_THRESHOLD
        self._recovery_seconds = (
            recovery_seconds if recovery_seconds is not None
            else settings.AI_AGENT_CIRCUIT_BREAKER_RECOVERY_SECONDS
        )
        self._memory_state: Dict[str, Dict[str, Any]] = {}

    async def allow(self, agent_type: str) -> bool:
        """判断是否允许新会话通过。closed 放行；open 超 recovery 转 half_open；
        half_open 用 SETNX 限制仅 1 次试探。返回 True 允许，False 拒绝。"""
        state = self._get_field(agent_type, "state", _CLOSED)
        if state == _CLOSED:
            return True
        if state == _OPEN:
            opened_at = self._get_field(agent_type, "opened_at")
            if opened_at is None:
                return False
            if time.time() - float(opened_at) >= self._recovery_seconds:
                self._set_field(agent_type, "state", _HALF_OPEN)
                return self._acquire_probe(agent_type)
            return False
        if state == _HALF_OPEN:
            return self._acquire_probe(agent_type)
        return True

    async def record_success(self, agent_type: str) -> None:
        """记录成功：closed 重置失败计数；half_open 转 closed 并清空状态。"""
        state = self._get_field(agent_type, "state", _CLOSED)
        if state == _CLOSED:
            self._set_field(agent_type, "failures", 0)
        elif state == _HALF_OPEN:
            self._clear_all(agent_type)

    async def record_failure(self, agent_type: str) -> None:
        """记录失败：closed 失败计数+1 达阈值转 open；half_open 转 open；open 忽略。"""
        state = self._get_field(agent_type, "state", _CLOSED)
        if state == _OPEN:
            return
        if state == _HALF_OPEN:
            self._set_field(agent_type, "state", _OPEN)
            self._set_field(agent_type, "opened_at", str(time.time()))
            self._set_field(agent_type, "failures", 0)
            self._clear_probe(agent_type)
            return
        failures = self._incr_failures(agent_type)
        if failures >= self._threshold:
            self._set_field(agent_type, "state", _OPEN)
            self._set_field(agent_type, "opened_at", str(time.time()))

    # ── 内部方法：Redis 优先，异常降级内存 ──
    def _key(self, agent_type: str, suffix: str) -> str:
        return _CB_KEY_PREFIX.format(agent_type=agent_type) + suffix

    def _try_redis(self, desc: str, op: Callable[[], T]) -> Optional[T]:
        if self._redis is None:
            return None
        try:
            return op()
        except Exception as e:
            logger.warning(f"Redis {desc}失败，降级内存: {e}")
            return None

    def _get_field(self, agent_type: str, suffix: str, default: Any = None) -> Any:
        val = self._try_redis(f"读取{suffix}", lambda: self._redis.get(self._key(agent_type, suffix)))
        return val if val is not None else self._memory_state.setdefault(agent_type, {}).get(suffix, default)

    def _set_field(self, agent_type: str, suffix: str, value: Any) -> None:
        if self._try_redis(f"写入{suffix}", lambda: self._redis.set(self._key(agent_type, suffix), value)) is None:
            self._memory_state.setdefault(agent_type, {})[suffix] = value

    def _incr_failures(self, agent_type: str) -> int:
        val = self._try_redis("累加失败计数", lambda: self._redis.incr(self._key(agent_type, "failures")))
        if val is not None:
            return int(val)
        state = self._memory_state.setdefault(agent_type, {})
        state["failures"] = state.get("failures", 0) + 1
        return state["failures"]

    def _acquire_probe(self, agent_type: str) -> bool:
        """half_open 状态获取试探权：SETNX，TTL=recovery_seconds，仅允许 1 次。"""
        key = self._key(agent_type, "probe")
        val = self._try_redis("SETNX 试探", lambda: self._redis.set(key, "1", nx=True, ex=self._recovery_seconds))
        if val is not None:
            return bool(val)
        state = self._memory_state.setdefault(agent_type, {})
        if state.get("probe_in_flight"):
            return False
        state["probe_in_flight"] = True
        return True

    def _clear_probe(self, agent_type: str) -> None:
        if self._try_redis("清空试探", lambda: self._redis.delete(self._key(agent_type, "probe"))) is None:
            self._memory_state.setdefault(agent_type, {})["probe_in_flight"] = False

    def _clear_all(self, agent_type: str) -> None:
        keys = [self._key(agent_type, s) for s in ("state", "failures", "opened_at", "probe")]
        if self._try_redis("清空熔断状态", lambda: self._redis.delete(*keys)) is None:
            self._memory_state.pop(agent_type, None)


__all__ = ["CircuitBreaker"]
