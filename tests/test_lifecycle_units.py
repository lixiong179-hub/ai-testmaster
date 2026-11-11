"""R4-2: 应用生命周期单元测试。

验证 `app/core/lifecycle.py` 中拆分出的启动/关闭单元：
    - 单元 1/2：目录初始化、数据库初始化被正确调用
    - 单元 3：默认管理员的三种分支（新建 / 已存在跳过 / 失败非致命）
    - 单元 4/5：调度器启停被正确调用
    - 编排：startup() 按序调用 4 个单元，shutdown() 关闭调度器

全部使用 mock，不触碰真实数据库与 APScheduler。
"""
from unittest.mock import MagicMock, patch

from app.core import lifecycle


def _fake_session(existing_admin=None):
    """构造 Session 替身：query().filter().first() 返回指定管理员。"""
    db = MagicMock()
    query = MagicMock()
    query.filter.return_value.first.return_value = existing_admin
    db.query.return_value = query
    return db


class TestStartupInitUnits:
    def test_startup_init_directories_calls_init_directories(self):
        with patch("app.core.lifecycle.init_directories") as mock_init:
            lifecycle.startup_init_directories()
        mock_init.assert_called_once()

    def test_startup_init_db_calls_init_db(self):
        with patch("app.core.lifecycle.init_db") as mock_init:
            lifecycle.startup_init_db()
        mock_init.assert_called_once()


class TestEnsureDefaultAdmin:
    def test_creates_admin_when_missing(self):
        """无 admin 账号时创建、提交并关闭会话。"""
        db = _fake_session(existing_admin=None)
        with patch("app.core.lifecycle.PrimarySessionLocal", return_value=db), \
                patch("app.core.lifecycle.get_password_hash", return_value="hashed"), \
                patch("app.core.lifecycle.settings") as mock_settings:
            mock_settings.ADMIN_INITIAL_PASSWORD = "pwd-from-settings"
            lifecycle.startup_ensure_default_admin()

        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.close.assert_called_once()
        created = db.add.call_args.args[0]
        assert created.username == "admin"
        assert created.password_hash == "hashed"
        assert created.is_superuser is True

    def test_skips_creation_when_admin_exists(self):
        """已存在 admin 时不重复创建，但仍关闭会话。"""
        db = _fake_session(existing_admin=MagicMock())
        with patch("app.core.lifecycle.PrimarySessionLocal", return_value=db), \
                patch("app.core.lifecycle.settings") as mock_settings:
            mock_settings.ADMIN_INITIAL_PASSWORD = "pwd"
            lifecycle.startup_ensure_default_admin()

        db.add.assert_not_called()
        db.commit.assert_not_called()
        db.close.assert_called_once()

    def test_failure_is_non_fatal(self):
        """会话异常必须被吞掉：回滚 + 关闭，且不向上抛出。"""
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        with patch("app.core.lifecycle.PrimarySessionLocal", return_value=db):
            lifecycle.startup_ensure_default_admin()  # 不应抛异常

        db.rollback.assert_called_once()
        db.close.assert_called_once()
        db.add.assert_not_called()

    def test_session_factory_failure_is_non_fatal(self):
        """连会话都建不起来时，同样不得中断启动。"""
        with patch("app.core.lifecycle.PrimarySessionLocal", side_effect=RuntimeError("no pool")):
            lifecycle.startup_ensure_default_admin()  # 不应抛异常


class TestSchedulerUnits:
    def test_startup_scheduler_calls_scheduler_service(self):
        with patch("app.services.scheduler_service.start_scheduler") as mock_start:
            lifecycle.startup_scheduler()
        mock_start.assert_called_once()

    def test_shutdown_scheduler_calls_scheduler_service(self):
        with patch("app.services.scheduler_service.shutdown_scheduler") as mock_shutdown:
            lifecycle.shutdown_scheduler()
        mock_shutdown.assert_called_once()

    def test_startup_lag_monitor_calls_replica_lag(self):
        with patch("app.db.replica_lag.start_lag_monitor") as mock_start:
            lifecycle.startup_lag_monitor()
        mock_start.assert_called_once()


class TestLifecycleOrchestration:
    async def test_startup_runs_units_in_order(self):
        """startup() 必须按 目录 → 数据库 → 管理员 → 调度器 → 延迟监控 的顺序执行。"""
        calls = []
        with patch.object(lifecycle, "startup_init_directories", lambda: calls.append("directories")), \
                patch.object(lifecycle, "startup_init_db", lambda: calls.append("db")), \
                patch.object(lifecycle, "startup_ensure_default_admin", lambda: calls.append("admin")), \
                patch.object(lifecycle, "startup_scheduler", lambda: calls.append("scheduler")), \
                patch.object(lifecycle, "startup_lag_monitor", lambda: calls.append("lag_monitor")):
            await lifecycle.startup()

        assert calls == ["directories", "db", "admin", "scheduler", "lag_monitor"]

    def test_shutdown_stops_scheduler(self):
        with patch.object(lifecycle, "shutdown_scheduler") as mock_shutdown:
            lifecycle.shutdown()
        mock_shutdown.assert_called_once()
