import pytest
from unittest.mock import patch, MagicMock

from app.utils.crypto import (
    encrypt_password,
    decrypt_password,
    mask_password,
    _get_encryption_config,
    _get_fernet,
    encrypt,
    decrypt,
)


class TestEncryptPassword:
    def test_encrypt_normal_password(self):
        encrypted = encrypt_password("my_password")
        assert encrypted != "my_password"
        assert encrypted.startswith("gAAAAA")

    def test_encrypt_empty_password(self):
        assert encrypt_password("") == ""

    def test_encrypt_special_characters(self):
        special = "P@$$w0rd!#%&*()_+-=[]{}|;':\",./<>?"
        encrypted = encrypt_password(special)
        decrypted = decrypt_password(encrypted)
        assert decrypted == special

    def test_encrypt_unicode_password(self):
        unicode_pwd = "密码测试123"
        encrypted = encrypt_password(unicode_pwd)
        decrypted = decrypt_password(encrypted)
        assert decrypted == unicode_pwd

    def test_encrypt_long_password(self):
        long_pwd = "a" * 1000
        encrypted = encrypt_password(long_pwd)
        decrypted = decrypt_password(encrypted)
        assert decrypted == long_pwd

    def test_encrypt_decrypt_roundtrip(self):
        original = "test_roundtrip_123"
        encrypted = encrypt_password(original)
        decrypted = decrypt_password(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertext(self):
        pwd = "same_password"
        enc1 = encrypt_password(pwd)
        enc2 = encrypt_password(pwd)
        assert enc1 != enc2

    def test_encrypt_fernet_failure_raises(self):
        with patch("app.utils.crypto._get_fernet", side_effect=Exception("fernet error")):
            with pytest.raises(ValueError, match="密码加密失败"):
                encrypt_password("test")


class TestDecryptPassword:
    def test_decrypt_empty_password(self):
        assert decrypt_password("") == ""

    def test_decrypt_non_encrypted_returns_as_is(self):
        plain = "already_plain_text"
        result = decrypt_password(plain)
        assert result == plain

    def test_decrypt_invalid_encrypted_raises(self):
        with pytest.raises(ValueError, match="密码解密失败"):
            decrypt_password("gAAAAAinvaliddata")

    def test_decrypt_valid_encrypted(self):
        encrypted = encrypt_password("hello")
        result = decrypt_password(encrypted)
        assert result == "hello"


class TestMaskPassword:
    def test_mask_normal_password(self):
        assert mask_password("secret123") == "******"

    def test_mask_empty_password(self):
        assert mask_password("") == ""

    def test_mask_none_password(self):
        assert mask_password(None) == ""

    def test_mask_encrypted_password(self):
        assert mask_password("gAAAAAlongencryptedstring") == "******"


class TestGetEncryptionConfig:
    def test_returns_tuple(self):
        key, salt = _get_encryption_config()
        assert isinstance(key, bytes)
        assert isinstance(salt, bytes)

    def test_prod_empty_key_raises(self):
        mock_settings = MagicMock()
        mock_settings.ENCRYPTION_KEY = ""
        mock_settings.ENVIRONMENT = "prod"
        with patch("app.core.config.settings", mock_settings):
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                _get_encryption_config()

    def test_prod_empty_salt_raises(self):
        mock_settings = MagicMock()
        mock_settings.ENCRYPTION_KEY = "valid_key"
        mock_settings.ENCRYPTION_SALT = ""
        mock_settings.ENVIRONMENT = "prod"
        with patch("app.core.config.settings", mock_settings):
            with pytest.raises(ValueError, match="ENCRYPTION_SALT"):
                _get_encryption_config()

    def test_dev_empty_key_generates(self):
        mock_settings = MagicMock()
        mock_settings.ENCRYPTION_KEY = ""
        mock_settings.ENVIRONMENT = "dev"
        with patch("app.core.config.settings", mock_settings):
            key, salt = _get_encryption_config()
            assert len(key) > 0

    def test_dev_empty_salt_generates(self):
        mock_settings = MagicMock()
        mock_settings.ENCRYPTION_KEY = "valid_key"
        mock_settings.ENCRYPTION_SALT = ""
        mock_settings.ENVIRONMENT = "dev"
        with patch("app.core.config.settings", mock_settings):
            key, salt = _get_encryption_config()
            assert len(salt) > 0


class TestGetFernet:
    def test_returns_fernet_instance(self):
        from cryptography.fernet import Fernet
        f = _get_fernet()
        assert isinstance(f, Fernet)


class TestConvenienceAliases:
    def test_encrypt_alias(self):
        assert encrypt is encrypt_password

    def test_decrypt_alias(self):
        assert decrypt is decrypt_password
