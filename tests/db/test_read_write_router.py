"""读写分离路由层单元测试（Phase 1 Task 2）

测试对象：app/db/router.py、app/db/replica_lag.py
依赖：mock settings 与 _has_slave_url，禁止真实 DB/Redis 调用
运行：python -m pytest tests/db/test_read_write_router.py -v --tb=short
"""
import time
from unittest.mock import MagicMock, patch

import pytest


class TestRouterSelectReadFactory:
    """路由层 _select_read_factory 决策逻辑测试。"""

    def test_disabled_returns_primary(self):
        """READ_WRITE_SPLIT_ENABLED=False 时强制走主库（灰度回退）。"""
        from app.db import router
        with patch.object(router.settings, "READ_WRITE_SPLIT_ENABLED", False):
            from app.db.database._engine import AsyncPrimarySessionLocal
            factory = router._select_read_factory(request=MagicMock())
            assert factory is AsyncPrimarySessionLocal

    def test_no_slave_url_returns_primary(self):
        """未配置 DATABASE_URL_SLAVE 时退化为主库（零行为变更）。"""
        from app.db import router
        with patch.object(router.settings, "READ_WRITE_SPLIT_ENABLED", True), \
                patch("app.db.router._has_slave_url", return_value=False):
            from app.db.database._engine import AsyncPrimarySessionLocal
            factory = router._select_read_factory(request=MagicMock())
            assert factory is AsyncPrimarySessionLocal

    def test_within_write_window_returns_primary(self):
        """写后读窗口内强制走主库（一致性优先）。"""
        from app.db import router
        with patch.object(router.settings, "READ_WRITE_SPLIT_ENABLED", True), \
                patch("app.db.router._has_slave_url", return_value=True), \
                patch("app.db.router._is_within_write_window", return_value=True), \
                patch("app.db.router._is_replica_lag_degraded", return_value=False):
            from app.db.database._engine import AsyncPrimarySessionLocal
            factory = router._select_read_factory(request=MagicMock())
            assert factory is AsyncPrimarySessionLocal

    def test_replica_lag_degraded_returns_primary(self):
        """主从延迟超阈值时降级走主库（避免脏读）。"""
        from app.db import router
        with patch.object(router.settings, "READ_WRITE_SPLIT_ENABLED", True), \
                patch("app.db.router._has_slave_url", return_value=True), \
                patch("app.db.router._is_within_write_window", return_value=False), \
                patch("app.db.router._is_replica_lag_degraded", return_value=True):
            from app.db.database._engine import AsyncPrimarySessionLocal
            factory = router._select_read_factory(request=MagicMock())
            assert factory is AsyncPrimarySessionLocal

    def test_normal_returns_secondary(self):
        """正常场景走从库（读 QPS 提升 ≥3x）。"""
        from app.db import router
        fake_secondary = MagicMock(name="AsyncSecondarySessionLocal")
        with patch.object(router.settings, "READ_WRITE_SPLIT_ENABLED", True), \
                patch("app.db.router._has_slave_url", return_value=True), \
                patch("app.db.router._is_within_write_window", return_value=False), \
                patch("app.db.router._is_replica_lag_degraded", return_value=False), \
                patch("app.db.router.get_async_secondary_session_local", return_value=fake_secondary):
            factory = router._select_read_factory(request=MagicMock())
            assert factory is fake_secondary


class TestWriteWindow:
    """写后读一致性窗口逻辑测试。"""

    def test_no_write_ts_returns_false(self):
        """无写时间戳时不在窗口内。"""
        from app.db import router
        with patch("app.db.router._get_write_timestamp", return_value=None):
            assert router._is_within_write_window() is False

    def test_within_window_returns_true(self):
        """写时间戳在窗口内返回 True。"""
        from app.db import router
        now = time.time()
        with patch("app.db.router._get_write_timestamp", return_value=now), \
                patch.object(router.settings, "READ_AFTER_WRITE_WINDOW_SECONDS", 5.0):
            assert router._is_within_write_window() is True

    def test_outside_window_returns_false(self):
        """写时间戳超出窗口返回 False。"""
        from app.db import router
        old_ts = time.time() - 10.0
        with patch("app.db.router._get_write_timestamp", return_value=old_ts), \
                patch.object(router.settings, "READ_AFTER_WRITE_WINDOW_SECONDS", 5.0):
            assert router._is_within_write_window() is False


class TestReplicaLagDegradation:
    """主从延迟降级逻辑测试。"""

    def test_no_lag_returns_false(self):
        """未启动监控（lag=None）时不降级。"""
        from app.db import replica_lag
        with patch.object(replica_lag, "get_current_lag", return_value=None):
            # 直接测试 router._is_replica_lag_degraded
            from app.db import router
            with patch("app.db.replica_lag.get_current_lag", return_value=None):
                assert router._is_replica_lag_degraded() is False

    def test_lag_below_threshold_returns_false(self):
        """延迟低于降级阈值时不降级。"""
        from app.db import router
        with patch.object(router.settings, "REPLICA_LAG_DEGRADE_SECONDS", 2.0), \
                patch("app.db.replica_lag.get_current_lag", return_value=0.3):
            assert router._is_replica_lag_degraded() is False

    def test_lag_above_threshold_returns_true(self):
        """延迟超过降级阈值时降级走主库。"""
        from app.db import router
        with patch.object(router.settings, "REPLICA_LAG_DEGRADE_SECONDS", 2.0), \
                patch("app.db.replica_lag.get_current_lag", return_value=3.5):
            assert router._is_replica_lag_degraded() is True


class TestReplicaLagMonitor:
    """从库延迟监控 probe_replica_lag 测试。"""

    def test_no_slave_url_returns_none(self):
        """未配置从库时返回 None。"""
        from app.db import replica_lag
        with patch("app.db.replica_lag._has_slave_url", return_value=False):
            assert replica_lag.probe_replica_lag() is None

    def test_probe_failure_returns_none(self):
        """采样失败时返回 None，不抛异常。"""
        from app.db import replica_lag
        with patch("app.db.replica_lag._has_slave_url", return_value=True), \
                patch("pymysql.connect", side_effect=Exception("connection refused")):
            assert replica_lag.probe_replica_lag() is None

    def test_probe_success_updates_current_lag(self):
        """采样成功时更新 _current_lag 缓存。"""
        from app.db import replica_lag
        # 重置缓存
        replica_lag._current_lag = None

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [None] * 50 + [1.5]
        mock_cursor.description = [(f"col_{i}",) for i in range(50)] + [("Seconds_Behind_Source",)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("app.db.replica_lag._has_slave_url", return_value=True), \
                patch("pymysql.connect", return_value=mock_conn), \
                patch("app.db.replica_lag._find_lag_column", return_value=50):
            lag = replica_lag.probe_replica_lag()
            assert lag == 1.5
            assert replica_lag.get_current_lag() == 1.5


class TestUrlParser:
    """从库 URL 解析工具函数测试。"""

    def test_parse_host(self):
        from app.db.replica_lag import _parse_host
        assert _parse_host("mysql+pymysql://user:pwd@mysql-replica:3306/ai_testmaster") == "mysql-replica:3306"

    def test_parse_user(self):
        from app.db.replica_lag import _parse_user
        assert _parse_user("mysql+pymysql://repl:pwd@mysql-replica:3306/ai_testmaster") == "repl"

    def test_parse_password(self):
        from app.db.replica_lag import _parse_password
        assert _parse_password("mysql+pymysql://repl:secret@mysql-replica:3306/ai_testmaster") == "secret"

    def test_parse_db(self):
        from app.db.replica_lag import _parse_db
        assert _parse_db("mysql+pymysql://repl:pwd@mysql-replica:3306/ai_testmaster?charset=utf8mb4") == "ai_testmaster"

    def test_find_lag_column_mysql8(self):
        from app.db.replica_lag import _find_lag_column
        cols = ["Replica_IO_State", "Source_Host", "Seconds_Behind_Source"]
        assert _find_lag_column(cols) == 2

    def test_find_lag_column_mysql57(self):
        from app.db.replica_lag import _find_lag_column
        cols = ["Slave_IO_State", "Master_Host", "Seconds_Behind_Master"]
        assert _find_lag_column(cols) == 2

    def test_find_lag_column_not_found(self):
        from app.db.replica_lag import _find_lag_column
        assert _find_lag_column(["foo", "bar"]) is None


class TestRequireMaster:
    """require_master 依赖标记测试。"""

    def test_sets_force_master_state(self):
        from app.db.router import require_master
        request = MagicMock()
        request.state = MagicMock()
        require_master(request)
        assert request.state.force_master is True


class TestWriteTimestampFallback:
    """写时间戳进程内兜底逻辑测试。"""

    def test_mark_and_get_via_fallback(self):
        from app.db import router
        # 清空 Redis 客户端缓存，强制使用 fallback
        with patch("app.db.router._redis_client", return_value=None):
            router._write_ts_fallback.clear()
            import asyncio
            asyncio.run(router._mark_write_timestamp())
            ts = router._get_write_timestamp()
            assert ts is not None
            assert abs(time.time() - ts) < 1.0
