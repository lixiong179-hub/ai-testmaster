import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import (
    create_database_engine,
    get_db,
    get_read_db,
    get_db_context,
    get_read_db_context,
    init_db,
    drop_db,
    check_db_connection,
    Base,
    primary_engine,
    secondary_engine,
    PrimarySessionLocal,
    SecondarySessionLocal,
)
from app.core.config import settings


class TestCreateDatabaseEngine:
    def test_create_engine_returns_engine(self):
        engine = create_database_engine(
            "sqlite:///:memory:",
            pool_size=5,
            pool_timeout=10,
            max_overflow=2,
        )
        assert engine is not None
        assert str(engine.url) == "sqlite:///:memory:"
        engine.dispose()

    def test_create_engine_default_params(self):
        engine = create_database_engine("sqlite:///:memory:")
        assert engine is not None
        engine.dispose()


class TestGetDb:
    def test_get_db_yields_session(self):
        engine = create_engine("sqlite:///:memory:")
        TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with patch("app.db.database._session.PrimarySessionLocal", TestSession):
            gen = get_db()
            db = next(gen)
            assert db is not None
            try:
                next(gen)
            except StopIteration:
                pass
            db.close()

    def test_get_db_exception_rollback(self):
        mock_session = MagicMock()

        with patch("app.db.database._session.PrimarySessionLocal", return_value=mock_session):
            gen = get_db()
            db = next(gen)
            assert db is not None
            try:
                gen.throw(Exception("db error"))
            except Exception:
                pass
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called()


class TestGetReadDb:
    def test_get_read_db_yields_session(self):
        engine = create_engine("sqlite:///:memory:")
        TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # 性能优化：secondary 引擎懒加载，测试改为 patch 工厂函数
        with patch("app.db.database._session.get_secondary_session_local", return_value=TestSession):
            gen = get_read_db()
            db = next(gen)
            assert db is not None
            try:
                next(gen)
            except StopIteration:
                pass
            db.close()

    def test_get_read_db_exception_rollback(self):
        mock_session = MagicMock()
        mock_session_local = MagicMock(return_value=mock_session)

        with patch("app.db.database._session.get_secondary_session_local", return_value=mock_session_local):
            gen = get_read_db()
            db = next(gen)
            try:
                gen.throw(Exception("read error"))
            except Exception:
                pass
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called()


class TestGetDbContext:
    def test_context_manager_success(self):
        mock_session = MagicMock()

        with patch("app.db.database._session.PrimarySessionLocal", return_value=mock_session):
            with get_db_context() as db:
                assert db is not None
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_context_manager_exception(self):
        mock_session = MagicMock()

        with patch("app.db.database._session.PrimarySessionLocal", return_value=mock_session):
            with pytest.raises(RuntimeError):
                with get_db_context() as db:
                    raise RuntimeError("context error")
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestGetReadDbContext:
    def test_context_manager_success(self):
        mock_session = MagicMock()
        mock_session_local = MagicMock(return_value=mock_session)

        # 性能优化：secondary 引擎懒加载，测试改为 patch 工厂函数
        with patch("app.db.database._session.get_secondary_session_local", return_value=mock_session_local):
            with get_read_db_context() as db:
                assert db is not None
            mock_session.close.assert_called_once()

    def test_context_manager_exception(self):
        mock_session = MagicMock()
        mock_session_local = MagicMock(return_value=mock_session)

        with patch("app.db.database._session.get_secondary_session_local", return_value=mock_session_local):
            with pytest.raises(RuntimeError):
                with get_read_db_context() as db:
                    raise RuntimeError("read context error")
            mock_session.close.assert_called_once()


class TestInitDb:
    @patch("app.db.database._init.primary_engine")
    @patch("app.db.database._init.Base")
    def test_init_db_creates_tables(self, mock_base, mock_engine):
        init_db()
        mock_base.metadata.create_all.assert_called_once_with(bind=mock_engine)

    @patch("app.db.database._init.primary_engine")
    @patch("app.db.database._init.Base")
    @patch("app.db.database._init.smart_sync_database", create=True)
    def test_init_db_smart_sync_success(self, mock_sync, mock_base, mock_engine):
        mock_sync.return_value = {"fixed": 0, "summary": "ok"}
        with patch.dict("sys.modules", {"app.db.smart_sync": MagicMock(smart_sync_database=mock_sync)}):
            init_db()

    @patch("app.db.database._init.primary_engine")
    @patch("app.db.database._init.Base")
    @patch("app.db.database._init.smart_sync_database", create=True)
    def test_init_db_smart_sync_with_fixes(self, mock_sync, mock_base, mock_engine):
        mock_sync.return_value = {"fixed": 3, "summary": "3 columns added"}
        with patch.dict("sys.modules", {"app.db.smart_sync": MagicMock(smart_sync_database=mock_sync)}):
            init_db()

    @patch("app.db.database._init.primary_engine")
    @patch("app.db.database._init.Base")
    def test_init_db_smart_sync_failure_non_fatal(self, mock_base, mock_engine):
        with patch("app.db.database._init.smart_sync_database", create=True) as mock_sync:
            mock_sync.side_effect = ImportError("no module")
            with patch.dict("sys.modules", {"app.db.smart_sync": None}):
                init_db()


class TestDropDb:
    @patch("app.db.database._init.primary_engine")
    @patch("app.db.database._init.Base")
    def test_drop_db(self, mock_base, mock_engine):
        drop_db()
        mock_base.metadata.drop_all.assert_called_once_with(bind=mock_engine)


class TestCheckDbConnection:
    def test_check_connection_success(self):
        engine = create_engine("sqlite:///:memory:")
        with patch("app.db.database._init.primary_engine", engine):
            result = check_db_connection()
            assert result is True

    def test_check_connection_failure(self):
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("connection failed")
        with patch("app.db.database._init.primary_engine", mock_engine):
            result = check_db_connection()
            assert result is False


class TestModuleLevelObjects:
    def test_base_exists(self):
        assert Base is not None

    def test_primary_engine_exists(self):
        assert primary_engine is not None

    def test_secondary_engine_exists(self):
        assert secondary_engine is not None

    def test_primary_session_local_exists(self):
        assert PrimarySessionLocal is not None

    def test_secondary_session_local_exists(self):
        assert SecondarySessionLocal is not None


# ==================== ModelBase 行为回归测试 ====================
# 变更 1 消除了 _engine.py 的 Base.__init__ 猴子补丁，改为通过
# declarative_base(cls=ModelBase, constructor=ModelBase.__init__) 注入。
# 以下测试锁定 ModelBase 的四项构造期契约，防止未来重构破坏隐式约定。

from sqlalchemy import Column as _MbColumn, Integer as _MbInteger, String as _MbString, Boolean as _MbBoolean, DateTime as _MbDateTime
from app.utils.db_time import utcnow as _mb_utcnow


class _ModelBaseDemo(Base):
    """ModelBase 行为验证专用模型。

    独立表名，不与业务表冲突；仅在测试中实例化，不持久化。
    """
    __tablename__ = "_test_modelbase_demo"
    __test__ = False

    id = _MbColumn(_MbInteger, primary_key=True)
    name = _MbColumn(_MbString(50), nullable=False)
    is_active = _MbColumn(_MbBoolean, default=False, nullable=False)
    status = _MbColumn(_MbString(20), default="pending", nullable=False)
    created_at = _MbColumn(_MbDateTime, default=_mb_utcnow)


class TestModelBase:
    """锁定 ModelBase 构造期行为，为变更 1（消除 Base.__init__ 猴子补丁）提供回归保护。

    覆盖四项契约：
    1. 非 callable 列默认值在实例化后立即可读（不等待 flush）。
    2. callable 列默认值不在实例化时预填（由 SQLAlchemy 在 flush 时触发）。
    3. 非列名 kwargs 通过 setattr 设置到实例，兼容历史调用约定。
    4. 列名 kwargs 正常透传到 SQLAlchemy _declarative_constructor。
    """

    def test_non_callable_default_is_prefilled(self):
        """非 callable 列默认值在实例化后立即可读，业务代码可在 add 前读取。"""
        obj = _ModelBaseDemo(name="demo")
        assert obj.is_active is False
        assert obj.status == "pending"

    def test_callable_default_not_prefilled(self):
        """callable 列默认值不在实例化时预填，由 SQLAlchemy 在 flush 时触发。"""
        obj = _ModelBaseDemo(name="demo")
        assert obj.created_at is None

    def test_extra_kwargs_set_via_setattr(self):
        """非列名 kwargs 被 setattr 设置到实例，兼容历史调用约定。"""
        obj = _ModelBaseDemo(name="demo", transient_flag="abc")
        assert obj.transient_flag == "abc"

    def test_column_kwargs_passed_through(self):
        """列名 kwargs 正常透传到 SQLAlchemy _declarative_constructor。"""
        obj = _ModelBaseDemo(name="demo", status="approved")
        assert obj.name == "demo"
        assert obj.status == "approved"
