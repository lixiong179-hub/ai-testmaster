"""通用 Token 预算守卫基类。

设计目的：
    自愈体系（app/services/self_healing/token_budget.py）、Agent 架构
    （app/services/agent/token_budget.py）、Visual AI 引擎三处都需要
    「单次 Token 上限 + 日预算 Redis 累计 + 内存降级」三件套。早期实现
    把这套逻辑硬编码在 self_healing 内，导致新场景重复造轮子且行为漂移。

抽象边界：
    BaseTokenBudgetGuard 只负责与 Redis / 内存降级交互的通用逻辑：
        - 按子类传入的 namespace 拼接 counter_key / marker_key
        - INCRBY 累计 + SETNX marker 标记首次写入 + EXPIRE 计数 key
        - Redis 异常时降级进程内内存计数（不阻断主流程）
    子类只需实现两个抽象方法，决定单次/日预算的配置来源：
        - check_single_call(token_estimate) -> bool
        - is_daily_budget_exhausted() -> bool

Redis key 约定：
    counter_key = f"{namespace}{YYYYMMDD}"
    marker_key  = f"{namespace}{YYYYMMDD}:marker"
    子类通过 namespace 实现隔离（self_heal:token: vs agent:token:{type}:{pid}:）

TTL 策略：
    默认 25h，确保跨时区的一天内 key 始终存活；仅首次写入 marker 时设置
    计数 key 的 TTL，避免持续刷新导致 key 永生。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from loguru import logger

# 默认 TTL（25h），跨时区覆盖一天
_DEFAULT_TTL_SECONDS: int = 25 * 3600


class BaseTokenBudgetGuard(ABC):
    """Token 预算守卫抽象基类。

    子类必须实现 check_single_call 与 is_daily_budget_exhausted，
    决定单次/日预算的配置来源（settings 哪个字段）。consume 为通用实现，
    按 namespace 隔离 Redis key。

    Attributes:
        _redis: 同步 redis.Redis 实例（推荐 decode_responses=True）；None 时走内存降级。
        _memory_counter: Redis 不可用时的进程内累计计数。
        _namespace: Redis key 前缀，子类通过构造函数注入实现隔离。
        _ttl_seconds: 计数 key 的 TTL（秒），默认 25h。
    """

    def __init__(
        self,
        redis_client: Optional[Any],
        *,
        namespace: str,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        """注入 Redis 客户端与 namespace。

        Args:
            redis_client: 同步 redis.Redis 实例；为 None 时直接走内存降级。
            namespace: Redis key 前缀，必须以冒号结尾以保证 key 可读性
                （如 "self_heal:token:" / "agent:token:gen:1:"）。
            ttl_seconds: 计数 key 的 TTL（秒），默认 25h。
        """
        self._redis = redis_client
        self._memory_counter: int = 0
        self._namespace = namespace
        self._ttl_seconds = ttl_seconds

    # ── 抽象方法：由子类决定 limit 与 daily_budget 的来源 ──
    @abstractmethod
    def check_single_call(self, token_estimate: int) -> bool:
        """校验单次 Token 预估是否超限。

        Args:
            token_estimate: 单次调用预估 Token 消耗。

        Returns:
            bool: True 表示预估超限，应熔断；False 表示在限额内可调用。
        """

    @abstractmethod
    def is_daily_budget_exhausted(self) -> bool:
        """判断当日累计消耗是否已超日预算。

        Returns:
            bool: True 表示日预算已耗尽，应降级为非 AI 策略。
        """

    # ── 通用实现：Redis 累计 + 内存降级 ──
    def consume(self, amount: int) -> None:
        """累计当日 Token 消耗到 Redis；Redis 异常时降级内存计数。

        实现：INCRBY 累计计数，SETNX marker 标记首次写入，
        仅首次写入时 EXPIRE 计数 key，避免持续刷新导致 key 永生。

        Args:
            amount: 本次消耗的 Token 数。
        """
        day = datetime.now().strftime("%Y%m%d")
        counter_key = self._build_counter_key(day)
        marker_key = self._build_marker_key(day)
        if self._redis is not None:
            try:
                pipe = self._redis.pipeline()
                pipe.incrby(counter_key, amount)
                pipe.set(marker_key, "1", nx=True, ex=self._ttl_seconds)
                results = pipe.execute()
                # results[1] 为 True 表示首次写入 marker，此时设置计数 key 的 TTL
                if results[1]:
                    self._redis.expire(counter_key, self._ttl_seconds)
                logger.debug(
                    f"Token 预算累计: key={counter_key} amount={amount}"
                )
                return
            except Exception as e:
                logger.warning(f"Redis 累计 Token 失败，降级内存计数: {e}")
        # 降级路径：进程内内存累计
        self._memory_counter += amount

    # ── 保护方法：供子类 is_daily_budget_exhausted 复用 ──
    def _get_consumed(self) -> int:
        """读取当日累计 Token 消耗。

        Redis 不可用或异常时返回内存计数，保证 is_daily_budget_exhausted
        在降级场景下仍可作出熔断决策。

        Returns:
            int: 当日累计 Token 消耗。
        """
        day = datetime.now().strftime("%Y%m%d")
        counter_key = self._build_counter_key(day)
        if self._redis is not None:
            try:
                val = self._redis.get(counter_key)
                return int(val) if val else 0
            except Exception as e:
                logger.warning(
                    f"Redis 读取 Token 计数失败，使用内存计数: {e}"
                )
                return self._memory_counter
        return self._memory_counter

    # ── 内部方法：key 拼接 ──
    def _build_counter_key(self, day: str) -> str:
        """构造日计数 Redis key：{namespace}{YYYYMMDD}。"""
        return f"{self._namespace}{day}"

    def _build_marker_key(self, day: str) -> str:
        """构造首次写入标记 Redis key：{namespace}{YYYYMMDD}:marker。"""
        return f"{self._namespace}{day}:marker"
