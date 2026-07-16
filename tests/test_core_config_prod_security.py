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


class TestProdWeakDefaultKeyPattern:
    """生产环境弱默认值模式密钥校验测试。

    验证 is_default_value() 检查（识别 your-/changeme/secret 等关键字）
    被正确应用到 JWT_SECRET_KEY / ENCRYPTION_KEY / ENCRYPTION_SALT，
    防止开发者使用 "your-secret-key-here-padding-to-32-chars" 等绕过长度检查的弱密钥。
    """

    def test_prod_weak_default_jwt_secret_key_raises(self, tmp_path):
        """prod 环境 JWT_SECRET_KEY 含 'your-' 关键字（长度足够）抛 ValueError。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="your-secret-key-here-padding-to-32-chars",
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="Authorization,Content-Type",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
                s._ensure_secret_keys()

    def test_prod_weak_default_encryption_key_raises(self, tmp_path):
        """prod 环境 ENCRYPTION_KEY 含 'changeme' 关键字抛 ValueError。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="changeme-encryption-key-padding-here",
            ENCRYPTION_SALT="already_set_salt_value",
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="Authorization,Content-Type",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                s._ensure_secret_keys()

    def test_prod_weak_default_encryption_salt_raises(self, tmp_path):
        """prod 环境 ENCRYPTION_SALT 含 'secret' 关键字抛 ValueError。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="my-secret-salt-value-padding-here",
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="Authorization,Content-Type",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with pytest.raises(ValueError, match="ENCRYPTION_SALT"):
                s._ensure_secret_keys()

    def test_prod_strong_random_keys_pass(self, tmp_path):
        """prod 环境强随机密钥（无弱模式关键字、长度足够）通过校验。"""
        import secrets
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="prod",
            DEEPSEEK_API_KEY="sk-real-key-not-default",
            JWT_SECRET_KEY=secrets.token_urlsafe(32),
            ENCRYPTION_KEY=secrets.token_urlsafe(32),
            ENCRYPTION_SALT=secrets.token_urlsafe(32),
            CORS_ORIGINS="https://prod.example.com",
            CORS_ALLOW_HEADERS="Authorization,Content-Type",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        # 校验通过即视为成功


class TestDevWeakDefaultKeyPatternWarns:
    """非生产环境弱默认值模式密钥应发出警告但不抛错。"""

    def test_dev_weak_default_jwt_secret_key_warns_not_raises(self, tmp_path, recwarn):
        """dev 环境 JWT_SECRET_KEY 含弱模式关键字发出 UserWarning 但不抛错。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="your-secret-key-here-padding-to-32-chars",
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            s._ensure_secret_keys()
        # 应至少有一条包含 JWT_SECRET_KEY 的警告
        warnings_text = " ".join(str(w.message) for w in recwarn.list)
        assert "JWT_SECRET_KEY" in warnings_text


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
