"""读写分离路由层（Phase 1 Task 2）

业务用途：GET 类只读端点路由至从库，主库写压力下降 ≥60%。
设计原则：
1. 未配置 DATABASE_URL_SLAVE 时自动退化为主库，零行为变更；
2. 主从延迟超过 REPLICA_LAG_DEGRADE_SECONDS 时自动降级走主库；
3. 写后读一致性窗口内的读强制走主库（基于 Redis 时间戳）。

路由策略：
- `get_async_write_session` / `get_async_read_session`：FastAPI 依赖注入
- `mark_write_timestamp`：写操作后记录时间戳，触发读主库窗口

配置预留（R2-2 / Q2）：读写分离降级为「配置预留」——仅保留 `DATABASE_URL_SLAVE`
与懒加载退化（未配置从库时全部读请求走主库，零行为变更）。按端点强制走主库的
旧依赖已删除（全仓零使用点，且路由层从未读取其标记，属死代码）；如需写后读强一致，
请使用 `READ_AFTER_WRITE_WINDOW_SECONDS` 写后读窗口（已生效）。
决策与删除理由见 `docs/architecture/paradigm-convergence-decision.md`。

依赖：app.db.database._engine 懒加载 secondary 引擎层
"""

import logging
import time
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database._engine import (
    AsyncPrimarySessionLocal,
    _has_slave_url,
    get_async_secondary_session_local,
)

logger = logging.getLogger(__name__)

# 写操作时间戳缓存键（Redis 可用时使用，否则降级为进程内 dict）
_WRITE_TS_KEY = "rws:last_write_ts"
_write_ts_fallback: dict[str, float] = {}


def _redis_client():
    """懒加载 Redis 客户端，失败时返回 None。"""
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
    except Exception:
        return None


async def get_async_write_session() -> AsyncIterator[AsyncSession]:
    """写会话：始终走主库。写后标记时间戳触发读主库窗口。"""
    async with AsyncPrimarySessionLocal() as session:
        try:
            yield session
        finally:
            await _mark_write_timestamp()


async def get_async_read_session(request: Request) -> AsyncIterator[AsyncSession]:
    """读会话：根据延迟、写后读窗口、配置开关动态选择主/从库。

    边界场景：
    1. READ_WRITE_SPLIT_ENABLED=False → 主库（灰度回退）
    2. 未配置 DATABASE_URL_SLAVE → 主库（零行为变更）
    3. 写后读窗口内 → 主库（一致性优先）
    4. 主从延迟超过 REPLICA_LAG_DEGRADE_SECONDS → 主库（避免脏读）
    5. 上述均不命中 → 从库（读 QPS 提升 ≥3x）
    """
    factory = _select_read_factory(request)
    async with factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"异步只读会话错误: {e}")
            await session.rollback()
            raise


def _select_read_factory(request: Request):
    """选择读会话工厂，含降级与一致性逻辑。"""
    if not settings.READ_WRITE_SPLIT_ENABLED:
        return AsyncPrimarySessionLocal
    if not _has_slave_url():
        return AsyncPrimarySessionLocal
    if _is_within_write_window():
        logger.debug("写后读窗口内，读请求走主库")
        return AsyncPrimarySessionLocal
    if _is_replica_lag_degraded():
        logger.warning("主从延迟超阈值，读请求降级走主库")
        return AsyncPrimarySessionLocal
    return get_async_secondary_session_local()


def _is_within_write_window() -> bool:
    """检查是否在写后读一致性窗口内。"""
    last_ts = _get_write_timestamp()
    if last_ts is None:
        return False
    elapsed = time.time() - last_ts
    return elapsed < settings.READ_AFTER_WRITE_WINDOW_SECONDS


def _is_replica_lag_degraded() -> bool:
    """检查从库延迟是否超过降级阈值。

    实现：从 ReplicaLagMonitor 缓存读取最新延迟，未启动监控时返回 False。
    """
    from app.db.replica_lag import get_current_lag

    lag = get_current_lag()
    return lag is not None and lag > settings.REPLICA_LAG_DEGRADE_SECONDS


def _get_write_timestamp() -> float | None:
    """获取最近一次写操作时间戳（Redis 优先，进程内兜底）。"""
    client = _redis_client()
    if client is not None:
        try:
            ts = client.get(_WRITE_TS_KEY)
            if ts is not None:
                return float(ts)
            return None
        except Exception:
            pass
    return _write_ts_fallback.get("global")


async def _mark_write_timestamp() -> None:
    """记录写操作时间戳，触发读主库窗口。"""
    now = time.time()
    client = _redis_client()
    if client is not None:
        try:
            client.setex(_WRITE_TS_KEY, int(settings.READ_AFTER_WRITE_WINDOW_SECONDS * 2), now)
            return
        except Exception:
            pass
    _write_ts_fallback["global"] = now
