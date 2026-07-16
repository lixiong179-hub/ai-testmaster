import pytest
from unittest.mock import patch

from app.core.config import Settings


class TestProdWildcardCorsAllowHeaders:
    """生产环境 CORS_ALLOW_HEADERS 安全校验测试。"""

    def test_prod_wildcard_cors_allow_headers_raises(self, tmp_path):
        """验证 prod 环境 CORS_ALLOW_HEADERS="*" 抛 ValueError。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="*",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="CORS_ALLOW_HEADERS"):
                s._ensure_secret_keys()

    def test_prod_empty_cors_allow_headers_raises(self, tmp_path):
        """验证 prod 环境 CORS_ALLOW_HEADERS="" 抛 ValueError。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="CORS_ALLOW_HEADERS"):
                s._ensure_secret_keys()

    def test_prod_explicit_cors_allow_headers_passes(self, tmp_path):
        """验证 prod 环境显式 Header 列表通过校验（不抛错）。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="Authorization,Content-Type,Accept,Origin",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert "Authorization" in s.cors_allow_headers_list


class TestProdMissingJwtSecretKey:
    def test_prod_missing_jwt_secret_key_raises(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="",
            CORS_ORIGINS="https://prod.example.com",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
                s._ensure_secret_keys()


class TestProdMissingEncryptionKey:
    def test_prod_missing_encryption_key_raises(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.example.com",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                s._ensure_secret_keys()


class TestProdMissingEncryptionSalt:
    def test_prod_missing_encryption_salt_raises(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="",
            CORS_ORIGINS="https://prod.example.com",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="ENCRYPTION_SALT"):
                s._ensure_secret_keys()


class TestDevMissingKeysAutoGenerate:
    def test_dev_missing_jwt_secret_key_no_exception(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert len(s.JWT_SECRET_KEY) > 0

    def test_dev_missing_encryption_key_no_exception(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="already_set_jwt_value",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="already_set_salt_value",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert len(s.ENCRYPTION_KEY) > 0

    def test_dev_missing_encryption_salt_no_exception(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="already_set_jwt_value",
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert len(s.ENCRYPTION_SALT) > 0

    def test_dev_all_keys_missing_no_exception(self, tmp_path):
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        assert len(s.JWT_SECRET_KEY) > 0
        assert len(s.ENCRYPTION_KEY) > 0
        assert len(s.ENCRYPTION_SALT) > 0
