"""加密工具单元测试 - crypto"""
import os
import pytest
from app.utils.crypto import (
    encrypt_password, decrypt_password, mask_password,
    verify_password, encrypt, decrypt, _get_fernet, _get_encryption_config,
)


class TestEncryptDecryptPassword:
    def test_encrypt_decrypt_roundtrip(self):
        plain = "my_secret_password"
        encrypted = encrypt_password(plain)
        assert encrypted.startswith("gAAAAA")
        assert decrypt_password(encrypted) == plain

    def test_encrypt_empty_string(self):
        assert encrypt_password("") == ""

    def test_decrypt_empty_string(self):
        assert decrypt_password("") == ""

    def test_decrypt_plaintext_passthrough(self):
        assert decrypt_password("plaintext_value") == "plaintext_value"

    def test_encrypt_none_returns_empty(self):
        assert encrypt_password(None) == ""

    def test_decrypt_none_returns_empty(self):
        assert decrypt_password(None) == ""

    def test_aliases(self):
        assert encrypt is encrypt_password
        assert decrypt is decrypt_password

    def test_different_inputs_different_ciphertexts(self):
        e1 = encrypt_password("password1")
        e2 = encrypt_password("password2")
        assert e1 != e2


class TestMaskPassword:
    def test_mask_nonempty(self):
        assert mask_password("any_password") == "******"

    def test_mask_empty(self):
        assert mask_password("") == ""

    def test_mask_none(self):
        assert mask_password(None) == ""

    def test_mask_encrypted(self):
        encrypted = encrypt_password("test")
        assert mask_password(encrypted) == "******"


class TestVerifyPassword:
    def test_verify_correct(self):
        encrypted = encrypt_password("mypassword")
        assert verify_password("mypassword", encrypted) is True

    def test_verify_incorrect(self):
        encrypted = encrypt_password("mypassword")
        assert verify_password("wrongpassword", encrypted) is False

    def test_verify_both_empty(self):
        assert verify_password("", "") is True

    def test_verify_invalid_encrypted(self):
        assert verify_password("test", "not_valid_encrypted") is False

    def test_verify_corrupt_ciphertext_raises_and_returns_false(self):
        result = verify_password("test", "gAAAAA-invalid-corrupt-data===")
        assert result is False


class TestDecryptCorruptCiphertext:
    def test_decrypt_corrupt_gAAAAA_raises_valueerror(self):
        with pytest.raises(ValueError, match="解密失败"):
            decrypt_password("gAAAAA-invalid-corrupt-data===")

    def test_decrypt_valid_ciphertext_succeeds(self):
        encrypted = encrypt_password("test")
        assert decrypt_password(encrypted) == "test"


class TestGetFernet:
    def test_fernet_instance(self):
        f = _get_fernet()
        assert f is not None
        token = f.encrypt(b"test")
        assert f.decrypt(token) == b"test"


class TestProductionKeyValidation:
    """测试生产环境缺少 ENCRYPTION_KEY/SALT 时必须报错�?

    直接修改 app.core.config.settings 单例的属性，
    触发 _get_encryption_config 中的生产环境校验逻辑�?
    """

    def test_production_missing_key_raises_valueerror(self):
        from app.core.config import settings

        original_env = settings.ENVIRONMENT
        original_key = settings.ENCRYPTION_KEY
        original_salt = settings.ENCRYPTION_SALT

        settings.ENVIRONMENT = "prod"
        settings.ENCRYPTION_KEY = ""
        settings.ENCRYPTION_SALT = "some_salt"
        try:
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                _get_encryption_config()
        finally:
            settings.ENVIRONMENT = original_env
            settings.ENCRYPTION_KEY = original_key
            settings.ENCRYPTION_SALT = original_salt

    def test_production_missing_salt_raises_valueerror(self):
        from app.core.config import settings

        original_env = settings.ENVIRONMENT
        original_key = settings.ENCRYPTION_KEY
        original_salt = settings.ENCRYPTION_SALT

        settings.ENVIRONMENT = "prod"
        settings.ENCRYPTION_KEY = "some_key"
        settings.ENCRYPTION_SALT = ""
        try:
            with pytest.raises(ValueError, match="ENCRYPTION_SALT"):
                _get_encryption_config()
        finally:
            settings.ENVIRONMENT = original_env
            settings.ENCRYPTION_KEY = original_key
            settings.ENCRYPTION_SALT = original_salt


class TestEncryptPasswordError:
    """测试加密失败时拒绝存储明文�?

    通过临时�?settings.ENVIRONMENT 设为 prod 且清�?ENCRYPTION_KEY�?
    �?_get_encryption_config 抛出 ValueError，触�?encrypt_password 的异常捕获�?
    """

    def test_encrypt_password_config_failure_raises_valueerror(self):
        from app.core.config import settings

        original_env = settings.ENVIRONMENT
        original_key = settings.ENCRYPTION_KEY
        original_salt = settings.ENCRYPTION_SALT

        settings.ENVIRONMENT = "prod"
        settings.ENCRYPTION_KEY = ""
        settings.ENCRYPTION_SALT = ""
        try:
            with pytest.raises(ValueError, match="加密失败"):
                encrypt_password("some_password")
        finally:
            settings.ENVIRONMENT = original_env
            settings.ENCRYPTION_KEY = original_key
            settings.ENCRYPTION_SALT = original_salt
