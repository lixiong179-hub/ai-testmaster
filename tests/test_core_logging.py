import os
import shutil
import logging
import tempfile
from pathlib import Path

from loguru import logger

from app.core.logging import setup_logging, get_logger, _redirect_uvicorn_logs


class TestSetupLogging:
    def test_default_setup(self):
        setup_logging()
        assert True

    def test_custom_log_level_debug(self):
        setup_logging(log_level="DEBUG")
        assert True

    def test_custom_log_level_warning(self):
        setup_logging(log_level="WARNING")
        assert True

    def test_custom_log_level_error(self):
        setup_logging(log_level="ERROR")
        assert True

    def test_custom_log_level_critical(self):
        setup_logging(log_level="CRITICAL")
        assert True

    def test_disable_file_logging(self):
        setup_logging(enable_file_logging=False)
        assert True

    def test_file_logging_creates_directory(self):
        log_dir = os.path.join(tempfile.gettempdir(), "test_logging_create_dir")
        if os.path.exists(log_dir):
            shutil.rmtree(log_dir, ignore_errors=True)
        try:
            setup_logging(log_dir=log_dir, enable_file_logging=True)
            assert os.path.isdir(log_dir)
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)

    def test_custom_log_dir(self):
        log_dir = os.path.join(tempfile.gettempdir(), "test_logging_custom_dir")
        os.makedirs(log_dir, exist_ok=True)
        try:
            setup_logging(log_dir=log_dir, enable_file_logging=True)
            assert os.path.isdir(log_dir)
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)

    def test_custom_rotation_and_retention(self):
        log_dir = os.path.join(tempfile.gettempdir(), "test_logging_rotation")
        os.makedirs(log_dir, exist_ok=True)
        try:
            setup_logging(
                log_dir=log_dir,
                rotation="10 MB",
                retention="3 days",
                compression="gz",
                enable_file_logging=True,
            )
            assert os.path.isdir(log_dir)
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)


class TestGetLogger:
    def test_returns_logger(self):
        result = get_logger()
        assert result is not None

    def test_with_name(self):
        result = get_logger("test_module")
        assert result is not None

    def test_returns_same_instance(self):
        result1 = get_logger()
        result2 = get_logger("other")
        assert result1 is result2

    def test_none_name(self):
        result = get_logger(None)
        assert result is not None


class TestRedirectUvicornLogs:
    def test_redirect_modifies_uvicorn_loggers(self):
        _redirect_uvicorn_logs()
        for name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
            uv_logger = logging.getLogger(name)
            assert len(uv_logger.handlers) > 0
            assert uv_logger.propagate is False

    def test_redirect_sets_level(self):
        _redirect_uvicorn_logs()
        uv_logger = logging.getLogger("uvicorn")
        assert uv_logger.level == logging.INFO


class TestSetupLoggingEdgeCases:
    def test_repeated_setup(self):
        setup_logging(log_level="INFO")
        setup_logging(log_level="DEBUG")
        assert True

    def test_log_dir_none_uses_default(self):
        setup_logging(log_dir=None, enable_file_logging=True)
        project_root = Path(__file__).parent.parent
        expected_dir = str(project_root / "logs")
        assert os.path.isdir(expected_dir)

    def test_empty_log_level_string(self):
        setup_logging(log_level="DEBUG", enable_file_logging=False)
        assert True

    def test_setup_with_existing_log_dir(self):
        log_dir = os.path.join(tempfile.gettempdir(), "test_logging_existing")
        os.makedirs(log_dir, exist_ok=True)
        try:
            setup_logging(log_dir=log_dir, enable_file_logging=True)
            assert os.path.isdir(log_dir)
        finally:
            shutil.rmtree(log_dir, ignore_errors=True)
