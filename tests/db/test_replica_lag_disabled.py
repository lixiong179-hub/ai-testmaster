"""R2-2: 未配置从库（DATABASE_URL_SLAVE）时的零开销保证。

读写分离已降级为「配置预留」：未配置从库时，延迟监控必须**提前退出**，
既不起后台线程，也不建立任何从库连接，避免为未启用的能力付出运行时代价。

对应清单 R2-2 判据 1：
    - `start_lag_monitor()` 不启动后台线程（或显式提前 return）
    - `get_current_lag()` 返回 None 且不建立从库连接（create_engine 零调用）
"""
import threading
from unittest.mock import patch

from app.db import replica_lag


class TestLagMonitorDisabled:
    """未配置 slave 时的零开销行为。"""

    def test_start_lag_monitor_returns_without_thread(self):
        """未配置 slave：直接返回，不构造 APScheduler、不新增线程。"""
        before = threading.active_count()
        with patch.object(replica_lag, "_has_slave_url", return_value=False), \
                patch("apscheduler.schedulers.background.BackgroundScheduler") as mock_scheduler:
            result = replica_lag.start_lag_monitor()

        assert result is None
        mock_scheduler.assert_not_called()
        assert threading.active_count() == before

    def test_probe_replica_lag_skips_without_slave(self):
        """未配置 slave：采样函数直接返回 None，不建立连接。"""
        with patch.object(replica_lag, "_has_slave_url", return_value=False), \
                patch("pymysql.connect") as mock_connect:
            assert replica_lag.probe_replica_lag() is None

        mock_connect.assert_not_called()

    def test_get_current_lag_returns_none_without_connection(self):
        """`get_current_lag()` 只读内存态：返回 None 且不触发任何建连。"""
        original = replica_lag._current_lag
        replica_lag._current_lag = None
        try:
            with patch("pymysql.connect") as mock_connect, \
                    patch("sqlalchemy.create_engine") as mock_create_engine:
                assert replica_lag.get_current_lag() is None
            mock_connect.assert_not_called()
            mock_create_engine.assert_not_called()
        finally:
            replica_lag._current_lag = original

    def test_has_slave_url_false_when_unset(self, monkeypatch):
        """`DATABASE_URL_SLAVE` 为空 → `_has_slave_url()` 为 False。"""
        from app.core.config import settings
        from app.db.database._engine import _has_slave_url

        monkeypatch.setattr(settings, "DATABASE_URL_SLAVE", "")
        assert _has_slave_url() is False
