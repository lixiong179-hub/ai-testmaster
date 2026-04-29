"""加密工具单元测试 - crypto"""
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
        """Non-encrypted (no gAAAAA prefix) data is returned as-is."""
        assert decrypt_password("plaintext_value") == "plaintext_value"

    def test_encrypt_none_returns_empty(self):
        assert encrypt_password(None) == ""

    def test_decrypt_none_returns_empty(self):
        assert decrypt_password(None) == ""

    def test_aliases(self):
        """encrypt/decrypt are aliases for encrypt_password/decrypt_password."""
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
        """损坏的 Fernet 密文 (以 gAAAAA 开头但内容损坏) 应触发 ValueError 并返回 False"""
        # gAAAAA 开头但不是有效 Fernet token
        result = verify_password("test", "gAAAAA-invalid-corrupt-data===")
        assert result is False


class TestDecryptCorruptCiphertext:
    def test_decrypt_corrupt_gAAAAA_raises_valueerror(self):
        """损坏的 Fernet 密文应抛出 ValueError (line 144-146)"""
        with pytest.raises(ValueError, match="解密失败"):
            decrypt_password("gAAAAA-invalid-corrupt-data===")

    def test_decrypt_valid_ciphertext_succeeds(self):
        encrypted = encrypt_password("test")
        assert decrypt_password(encrypted) == "test"


class TestGetFernet:
    def test_fernet_instance(self):
        f = _get_fernet()
        assert f is not None
        # Can encrypt/decrypt with it
        token = f.encrypt(b"test")
        assert f.decrypt(token) == b"test"


class TestProductionKeyValidation:
    """测试生产环境缺少 ENCRYPTION_KEY/SALT 时必须报错 (line 55-59, 62-66)"""

    def test_production_missing_key_raises_valueerror(self):
        from unittest.mock import patch, MagicMock
        mock_settings = MagicMock()
        mock_settings.ENVIRONMENT = "production"
        mock_settings.ENCRYPTION_KEY = ""
        mock_settings.ENCRYPTION_SALT = "some_salt"

        # _get_encryption_config does `from app.core.config import settings` inside the function
        # We need to patch the import target
        with patch("app.core.config.settings", mock_settings):
            from app.utils.crypto import _get_encryption_config
            with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
                _get_encryption_config()

    def test_production_missing_salt_raises_valueerror(self):
        from unittest.mock import patch, MagicMock
        mock_settings = MagicMock()
        mock_settings.ENVIRONMENT = "production"
        mock_settings.ENCRYPTION_KEY = "some_key"
        mock_settings.ENCRYPTION_SALT = ""

        with patch("app.core.config.settings", mock_settings):
            from app.utils.crypto import _get_encryption_config
            with pytest.raises(ValueError, match="ENCRYPTION_SALT"):
                _get_encryption_config()


class TestEncryptPasswordError:
    """测试加密失败时拒绝存储明文 (line 114-116)"""

    def test_encrypt_password_fernet_failure_raises_valueerror(self):
        from unittest.mock import patch
        with patch("app.utils.crypto._get_fernet", side_effect=Exception("Fernet init failed")):
            with pytest.raises(ValueError, match="加密失败"):
                encrypt_password("some_password")
