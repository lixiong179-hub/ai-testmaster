"""密钥来源审计日志测试模块。

验证 app.core.key_management.ensure_secret_keys 在处理三个密钥
（JWT_SECRET_KEY / ENCRYPTION_KEY / ENCRYPTION_SALT）时，
正确记录密钥来源审计日志 [KEY_AUDIT]。
"""
import json
import logging
from unittest.mock import patch

import pytest

from app.core.config import Settings


class TestKeySourceAuditLog:
    """密钥来源审计日志测试。"""

    def test_key_source_env_logged(self, tmp_path, caplog):
        """密钥已通过环境变量设置时，记录 source=env（INFO 级别）。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="already_set_jwt_value_from_env",
            ENCRYPTION_KEY="already_set_key_value",
            ENCRYPTION_SALT="already_set_salt_value",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with caplog.at_level(logging.INFO, logger="app.core.key_management"):
                s._ensure_secret_keys()

        jwt_logs = [r for r in caplog.records if "KEY_AUDIT" in r.message and "JWT_SECRET_KEY" in r.message]
        assert len(jwt_logs) == 1
        assert "source=env" in jwt_logs[0].message
        assert jwt_logs[0].levelno == logging.INFO
        assert "AUTO_GENERATED" not in jwt_logs[0].message

    def test_key_source_cache_logged(self, tmp_path, caplog):
        """密钥从缓存文件加载时，记录 source=cache（INFO 级别）。"""
        cache_file = tmp_path / ".secret_keys"
        cache_data = {
            "jwt_secret_key": "cached_jwt_key_value_1234567890123456",
            "encryption_key": "cached_enc_key_value",
            "encryption_salt": "cached_salt_value",
        }
        cache_file.write_text(json.dumps(cache_data))

        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with caplog.at_level(logging.INFO, logger="app.core.key_management"):
                s._ensure_secret_keys()

        cache_logs = [r for r in caplog.records if "KEY_AUDIT" in r.message and "source=cache" in r.message]
        assert len(cache_logs) == 3
        for log_record in cache_logs:
            assert log_record.levelno == logging.INFO
            assert "AUTO_GENERATED" not in log_record.message

    def test_key_source_auto_generated_logged_with_warning(self, tmp_path, caplog):
        """密钥自动生成时，记录 source=auto-generated AUTO_GENERATED（WARNING 级别）。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with caplog.at_level(logging.WARNING, logger="app.core.key_management"):
                s._ensure_secret_keys()

        auto_gen_logs = [r for r in caplog.records if "KEY_AUDIT" in r.message and "auto-generated" in r.message]
        assert len(auto_gen_logs) == 3
        for log_record in auto_gen_logs:
            assert log_record.levelno == logging.WARNING
            assert "AUTO_GENERATED" in log_record.message

    def test_all_three_keys_sources_logged(self, tmp_path, caplog):
        """三个密钥的来源均被记录，且 key 名称正确。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with caplog.at_level(logging.INFO, logger="app.core.key_management"):
                s._ensure_secret_keys()

        key_audit_logs = [r for r in caplog.records if "KEY_AUDIT" in r.message]
        logged_keys = {r.message.split("key=")[1].split(" ")[0] for r in key_audit_logs}
        assert logged_keys == {"JWT_SECRET_KEY", "ENCRYPTION_KEY", "ENCRYPTION_SALT"}

    def test_mixed_key_sources_logged_correctly(self, tmp_path, caplog):
        """混合来源场景：JWT 来自 env、ENCRYPTION_KEY 来自 cache、ENCRYPTION_SALT 自动生成。"""
        cache_file = tmp_path / ".secret_keys"
        cache_file.write_text(json.dumps({"encryption_key": "cached_enc_key_value"}))

        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="jwt_from_env_value",
            ENCRYPTION_KEY="",
            ENCRYPTION_SALT="",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with caplog.at_level(logging.INFO, logger="app.core.key_management"):
                s._ensure_secret_keys()

        key_audit_logs = [r for r in caplog.records if "KEY_AUDIT" in r.message]

        jwt_log = next(r for r in key_audit_logs if "JWT_SECRET_KEY" in r.message)
        assert "source=env" in jwt_log.message
        assert jwt_log.levelno == logging.INFO

        enc_key_log = next(r for r in key_audit_logs if "ENCRYPTION_KEY" in r.message)
        assert "source=cache" in enc_key_log.message
        assert enc_key_log.levelno == logging.INFO

        enc_salt_log = next(r for r in key_audit_logs if "ENCRYPTION_SALT" in r.message)
        assert "source=auto-generated" in enc_salt_log.message
        assert enc_salt_log.levelno == logging.WARNING
        assert "AUTO_GENERATED" in enc_salt_log.message

    def test_audit_log_does_not_leak_key_value(self, tmp_path, caplog):
        """审计日志不记录密钥值本身，避免日志泄露。"""
        s = Settings(
            DATABASE_URL="mysql+pymysql://root:pass@localhost/db",
            ENVIRONMENT="dev",
            JWT_SECRET_KEY="super_secret_jwt_value_1234567890",
            ENCRYPTION_KEY="super_secret_enc_key",
            ENCRYPTION_SALT="super_secret_salt",
        )
        with patch("app.core.key_management.BASE_DIR", tmp_path):
            with caplog.at_level(logging.INFO, logger="app.core.key_management"):
                s._ensure_secret_keys()

        for record in caplog.records:
            assert "super_secret" not in record.message
