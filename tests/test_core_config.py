import pytest
import os
import json
import warnings
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.core.config import (
    parse_list,
    _generate_secret_key,
    Settings,
    DevSettings,
    TestSettings,
    ProdSettings,
    get_settings,
    init_directories,
    BASE_DIR,
)


class TestParseList:
    def test_list_input(self):
        assert parse_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_json_string_input(self):
        assert parse_list('["x", "y"]') == ["x", "y"]

    def test_comma_separated_string(self):
        assert parse_list("a, b, c") == ["a", "b", "c"]

    def test_comma_separated_with_empty_items(self):
        assert parse_list("a,,b,") == ["a", "b"]

    def test_single_value_string(self):
        assert parse_list("hello") == ["hello"]

    def test_invalid_json_falls_back_to_comma(self):
        assert parse_list("[invalid") == ["[invalid"]

    def test_none_input(self):
        assert parse_list(None) == []

    def test_int_input(self):
        assert parse_list(123) == []

    def test_empty_string(self):
        assert parse_list("") == []

    def test_empty_list(self):
        assert parse_list([]) == []


class TestGenerateSecretKey:
    def test_generates_non_empty_key(self):
        key = _generate_secret_key()
        assert len(key) > 20

    def test_generates_unique_keys(self):
        key1 = _generate_secret_key()
        key2 = _generate_secret_key()
        assert key1 != key2


class TestSettingsProperties:
    def test_allowed_extensions_list(self):
        s = Settings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db")
        result = s.allowed_extensions_list
        assert isinstance(result, list)
        assert len(result) > 0

    def test_cors_origins_list(self):
        s = Settings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db", CORS_ORIGINS="http://a.com,http://b.com")
        result = s.cors_origins_list
        assert "http://a.com" in result
        assert "http://b.com" in result

    def test_cors_allow_methods_list(self):
        s = Settings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db")
        result = s.cors_allow_methods_list
        assert "GET" in result

    def test_cors_allow_headers_list(self):
        s = Settings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db", CORS_ALLOW_HEADERS="Content-Type,Authorization")
        result = s.cors_allow_headers_list
        assert "Content-Type" in result

    def test_celery_accept_content_list(self):
        s = Settings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db")
        result = s.celery_accept_content_list
        assert "json" in result


class TestEnsureSecretKeys:
    def test_empty_database_url_raises(self):
        s = Settings(DATABASE_URL="")
        with pytest.raises(ValueError, match="DATABASE_URL 未配置"):
            s._ensure_secret_keys()

    def test_sqlite_database_url_raises(self):
        s = Settings(DATABASE_URL="sqlite:///test.db")
        with pytest.raises(ValueError, match="禁止使用 SQLite"):
            s._ensure_secret_keys()

    def test_prod_default_api_key_raises(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="your-api-key-here",
            JWT_SECRET_KEY="a" * 32,
            CORS_ORIGINS="https://prod.com",
        )
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            s._ensure_secret_keys()

    def test_prod_short_jwt_key_raises(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="short",
            CORS_ORIGINS="https://prod.com",
        )
        with pytest.raises(ValueError, match="JWT_SECRET_KEY长度不足"):
            s._ensure_secret_keys()

    def test_prod_wildcard_cors_raises(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            CORS_ORIGINS="*",
        )
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            s._ensure_secret_keys()

    def test_prod_empty_cors_raises(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            CORS_ORIGINS="",
        )
        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            s._ensure_secret_keys()

    def test_dev_default_api_key_warns(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            DEEPSEEK_API_KEY="changeme",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s._ensure_secret_keys()
            assert any("DEEPSEEK_API_KEY" in str(warning.message) for warning in w)

    def test_dev_empty_api_key_warns(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            DEEPSEEK_API_KEY="",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s._ensure_secret_keys()
            assert any("DEEPSEEK_API_KEY" in str(warning.message) for warning in w)

    def test_prod_empty_api_key_raises(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="",
            JWT_SECRET_KEY="a" * 32,
            CORS_ORIGINS="https://prod.com",
        )
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            s._ensure_secret_keys()

    def test_auto_generate_jwt_key(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
        )
        s._ensure_secret_keys()
        assert len(s.JWT_SECRET_KEY) > 0

    def test_auto_generate_encryption_key(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            ENCRYPTION_KEY="",
        )
        s._ensure_secret_keys()
        assert len(s.ENCRYPTION_KEY) > 0

    def test_auto_generate_encryption_salt(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            ENCRYPTION_SALT="",
        )
        s._ensure_secret_keys()
        assert len(s.ENCRYPTION_SALT) > 0

    def test_prod_auto_generate_jwt_warns(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            CORS_ORIGINS="https://prod.com",
        )
        s.JWT_SECRET_KEY = ""
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="JWT_SECRET_KEY长度不足"):
                s._ensure_secret_keys()

    def test_prod_auto_generate_encryption_key_warns(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.com",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                s._ensure_secret_keys()

    def test_prod_auto_generate_encryption_salt_warns(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="",
            CORS_ORIGINS="https://prod.com",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="ENCRYPTION_SALT"):
                s._ensure_secret_keys()

    def test_cached_key_loading(self, tmp_path):
        cache_file = tmp_path / ".secret_keys"
        cache_data = {"jwt_secret_key": "cached_jwt_key_value_1234567890123456", "encryption_key": "cached_enc_key", "encryption_salt": "cached_salt"}
        cache_file.write_text(json.dumps(cache_data))

        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert s.JWT_SECRET_KEY == "cached_jwt_key_value_1234567890123456"
        assert s.ENCRYPTION_KEY == "cached_enc_key"
        assert s.ENCRYPTION_SALT == "cached_salt"

    def test_corrupted_cache_file_falls_back(self, tmp_path):
        cache_file = tmp_path / ".secret_keys"
        cache_file.write_text("not valid json{{{")

        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert len(s.JWT_SECRET_KEY) > 0

    def test_cache_file_with_empty_value_falls_back(self, tmp_path):
        cache_file = tmp_path / ".secret_keys"
        cache_file.write_text(json.dumps({"jwt_secret_key": ""}))

        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert len(s.JWT_SECRET_KEY) > 0

    def test_save_cached_key_failure_warns(self, tmp_path):
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        cache_file = readonly_dir / ".secret_keys"
        cache_file.write_text(json.dumps({"jwt_secret_key": ""}))
        cache_file.chmod(0o444)

        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
        )
        with patch("app.core.key_management.BASE_DIR", readonly_dir):
            with warnings.catch_warnings(record=True):
                warnings.simplefilter("always")
                s._ensure_secret_keys()

    def test_default_value_detection_patterns(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            DEEPSEEK_API_KEY="test1234",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s._ensure_secret_keys()
            assert any("DEEPSEEK_API_KEY" in str(warning.message) for warning in w)

    def test_is_default_value_secret_pattern(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            DEEPSEEK_API_KEY="xxx",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s._ensure_secret_keys()
            assert any("DEEPSEEK_API_KEY" in str(warning.message) for warning in w)

    def test_is_default_value_here_pattern(self):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            DEEPSEEK_API_KEY="put-your-key-here",
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s._ensure_secret_keys()
            assert any("DEEPSEEK_API_KEY" in str(warning.message) for warning in w)


class TestDevSettings:
    def test_dev_settings_defaults(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "dev", "DEBUG": "true", "LOG_LEVEL": "DEBUG"}):
            s = DevSettings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db", ENVIRONMENT="dev", DEBUG=True, LOG_LEVEL="DEBUG")
            assert s.DEBUG is True
            assert s.ENVIRONMENT == "dev"
            assert s.LOG_LEVEL == "DEBUG"
            assert s.CORS_ORIGINS == "*"


class TestTestSettings:
    def test_test_settings_defaults(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            s = TestSettings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db", ENVIRONMENT="test", DEBUG=False)
            assert s.DEBUG is False
            assert s.ENVIRONMENT == "test"
            assert s.LOG_LEVEL == "INFO"


class TestProdSettings:
    def test_prod_settings_defaults(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "prod", "LOG_LEVEL": "WARNING", "CORS_ORIGINS": ""}):
            s = ProdSettings(DATABASE_URL="mysql+pymysql://root:pass@localhost/db", ENVIRONMENT="prod", DEBUG=False, LOG_LEVEL="WARNING", CORS_ORIGINS="")
            assert s.DEBUG is False
            assert s.ENVIRONMENT == "prod"
            assert s.LOG_LEVEL == "WARNING"
            assert s.CORS_ORIGINS == ""


class TestGetSettings:
    def test_get_settings_dev(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            result = get_settings()
            assert isinstance(result, DevSettings)

    def test_get_settings_test(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            result = get_settings()
            assert isinstance(result, TestSettings)

    def test_get_settings_prod(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            result = get_settings()
            assert isinstance(result, ProdSettings)

    def test_get_settings_default_is_dev(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENVIRONMENT", None)
            result = get_settings()
            assert isinstance(result, DevSettings)


class TestInitDirectories:
    def test_init_directories_creates_dirs(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        ui_proto_dir = str(tmp_path / "ui_prototypes")

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.UI_PROTOTYPE_UPLOAD_DIR = ui_proto_dir
            result = init_directories()

        assert len(result) >= 1
        assert Path(upload_dir).exists()

    def test_init_directories_existing_dirs(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        Path(upload_dir).mkdir(parents=True, exist_ok=True)

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = upload_dir
            mock_settings.UI_PROTOTYPE_UPLOAD_DIR = upload_dir
            result = init_directories()

        assert len(result) >= 1

    def test_init_directories_error_returns_empty(self):
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = "/nonexistent\x00bad/path"
            result = init_directories()
        assert result == []

    def test_init_directories_no_ui_prototype_attr(self, tmp_path):
        upload_dir = str(tmp_path / "uploads")
        with patch("app.core.config.settings") as mock_settings:
            del mock_settings.UI_PROTOTYPE_UPLOAD_DIR
            mock_settings.UPLOAD_DIR = upload_dir
            result = init_directories()
        assert isinstance(result, list)
