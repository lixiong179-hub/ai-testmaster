"""从库延迟监控（Phase 1 Task 2）

业务用途：周期性采样从库 Seconds_Behind_Master，供路由层降级决策。
设计原则：
1. 单线程后台任务，避免并发采样；
2. 采样失败不抛异常，保留上一次有效值；
3. 未配置 DATABASE_URL_SLAVE 时直接返回 None。

依赖：APScheduler 周期触发 + pymysql 直连从库执行 SHOW REPLICA STATUS
"""
import logging
import threading
import time
from typing import Optional

from app.core.config import settings
from app.db.database._engine import _has_slave_url

logger = logging.getLogger(__name__)

_current_lag: Optional[float] = None
_last_probe_at: float = 0.0
_lock = threading.Lock()


def get_current_lag() -> Optional[float]:
    """获取最近一次采样的从库延迟（秒）。"""
    return _current_lag


def probe_replica_lag() -> Optional[float]:
    """主动采样一次从库延迟。

    实现：直连从库执行 `SHOW REPLICA STATUS`（MySQL 8.0+）或
    `SHOW SLAVE STATUS`（MySQL 5.7），解析 Seconds_Behind_Master。
    返回 None 表示未配置从库或采样失败。
    """
    global _current_lag, _last_probe_at
    if not _has_slave_url():
        return None

    try:
        import pymysql
        conn = pymysql.connect(
            _parse_host(settings.DATABASE_URL_SLAVE),
            user=_parse_user(settings.DATABASE_URL_SLAVE),
            password=_parse_password(settings.DATABASE_URL_SLAVE),
            database=_parse_db(settings.DATABASE_URL_SLAVE),
            connect_timeout=2,
            read_timeout=2,
        )
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute("SHOW REPLICA STATUS")
                except pymysql.err.ProgrammingError:
                    cur.execute("SHOW SLAVE STATUS")
                row = cur.fetchone()
                if not row:
                    return None
                # Seconds_Behind_Master 通常在最后一列或倒数第二列
                # 兼容 MySQL 8.0（REPLICA）与 5.7（SLAVE）
                cols = [d[0] for d in cur.description]
                idx = _find_lag_column(cols)
                if idx is None:
                    return None
                value = row[idx]
                if value is None:
                    # NULL 表示复制未运行或未知
                    return None
                lag = float(value)
                with _lock:
                    _current_lag = lag
                    _last_probe_at = time.time()
                return lag
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"采样从库延迟失败: {e}")
        return None


def start_lag_monitor() -> None:
    """启动后台延迟监控（APScheduler 周期任务）。

    边界场景：APScheduler 未初始化时跳过，路由层降级逻辑失效但读请求仍可路由至从库。
    """
    if not _has_slave_url():
        logger.info("未配置 DATABASE_URL_SLAVE，跳过从库延迟监控启动")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            probe_replica_lag,
            trigger=IntervalTrigger(seconds=settings.REPLICA_LAG_PROBE_INTERVAL_SECONDS),
            id="replica_lag_probe",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.start()
        logger.info(
            f"从库延迟监控已启动，采样周期 {settings.REPLICA_LAG_PROBE_INTERVAL_SECONDS}s，"
            f"降级阈值 {settings.REPLICA_LAG_DEGRADE_SECONDS}s"
        )
    except Exception as e:
        logger.warning(f"启动从库延迟监控失败: {e}")


def _find_lag_column(cols: list[str]) -> Optional[int]:
    """兼容定位 Seconds_Behind_Master 列索引。"""
    for name in ("Seconds_Behind_Source", "Seconds_Behind_Master"):
        if name in cols:
            return cols.index(name)
    return None


def _parse_host(url: str) -> str:
    """从 mysql+pymysql://user:pwd@host:port/db 解析 host[:port]。"""
    try:
        auth, path = url.split("@", 1)
        return path.split("/", 1)[0]
    except Exception:
        return "localhost"


def _parse_user(url: str) -> str:
    try:
        scheme, rest = url.split("://", 1)
        auth, _ = rest.split("@", 1)
        return auth.split(":", 1)[0]
    except Exception:
        return "root"


def _parse_password(url: str) -> str:
    try:
        scheme, rest = url.split("://", 1)
        auth, _ = rest.split("@", 1)
        if ":" in auth:
            return auth.split(":", 1)[1]
        return ""
    except Exception:
        return ""


def _parse_db(url: str) -> str:
    try:
        auth, path = url.split("@", 1)
        if "/" in path:
            return path.split("/", 1)[1].split("?", 1)[0]
        return ""
    except Exception:
        return ""
