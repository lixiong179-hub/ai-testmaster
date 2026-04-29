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

        with patch("app.db.database.PrimarySessionLocal", TestSession):
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

        with patch("app.db.database.PrimarySessionLocal", return_value=mock_session):
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

        with patch("app.db.database.SecondarySessionLocal", TestSession):
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

        with patch("app.db.database.SecondarySessionLocal", return_value=mock_session):
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

        with patch("app.db.database.PrimarySessionLocal", return_value=mock_session):
            with get_db_context() as db:
                assert db is not None
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_context_manager_exception(self):
        mock_session = MagicMock()

        with patch("app.db.database.PrimarySessionLocal", return_value=mock_session):
            with pytest.raises(RuntimeError):
                with get_db_context() as db:
                    raise RuntimeError("context error")
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestGetReadDbContext:
    def test_context_manager_success(self):
        mock_session = MagicMock()

        with patch("app.db.database.SecondarySessionLocal", return_value=mock_session):
            with get_read_db_context() as db:
                assert db is not None
            mock_session.close.assert_called_once()

    def test_context_manager_exception(self):
        mock_session = MagicMock()

        with patch("app.db.database.SecondarySessionLocal", return_value=mock_session):
            with pytest.raises(RuntimeError):
                with get_read_db_context() as db:
                    raise RuntimeError("read context error")
            mock_session.close.assert_called_once()


class TestInitDb:
    @patch("app.db.database.primary_engine")
    @patch("app.db.database.Base")
    def test_init_db_creates_tables(self, mock_base, mock_engine):
        init_db()
        mock_base.metadata.create_all.assert_called_once_with(bind=mock_engine)

    @patch("app.db.database.primary_engine")
    @patch("app.db.database.Base")
    @patch("app.db.database.smart_sync_database", create=True)
    def test_init_db_smart_sync_success(self, mock_sync, mock_base, mock_engine):
        mock_sync.return_value = {"fixed": 0, "summary": "ok"}
        with patch.dict("sys.modules", {"app.db.smart_sync": MagicMock(smart_sync_database=mock_sync)}):
            init_db()

    @patch("app.db.database.primary_engine")
    @patch("app.db.database.Base")
    @patch("app.db.database.smart_sync_database", create=True)
    def test_init_db_smart_sync_with_fixes(self, mock_sync, mock_base, mock_engine):
        mock_sync.return_value = {"fixed": 3, "summary": "3 columns added"}
        with patch.dict("sys.modules", {"app.db.smart_sync": MagicMock(smart_sync_database=mock_sync)}):
            init_db()

    @patch("app.db.database.primary_engine")
    @patch("app.db.database.Base")
    def test_init_db_smart_sync_failure_non_fatal(self, mock_base, mock_engine):
        with patch("app.db.database.smart_sync_database", create=True) as mock_sync:
            mock_sync.side_effect = ImportError("no module")
            with patch.dict("sys.modules", {"app.db.smart_sync": None}):
                init_db()


class TestDropDb:
    @patch("app.db.database.primary_engine")
    @patch("app.db.database.Base")
    def test_drop_db(self, mock_base, mock_engine):
        drop_db()
        mock_base.metadata.drop_all.assert_called_once_with(bind=mock_engine)


class TestCheckDbConnection:
    def test_check_connection_success(self):
        engine = create_engine("sqlite:///:memory:")
        with patch("app.db.database.primary_engine", engine):
            result = check_db_connection()
            assert result is True

    def test_check_connection_failure(self):
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("connection failed")
        with patch("app.db.database.primary_engine", mock_engine):
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
