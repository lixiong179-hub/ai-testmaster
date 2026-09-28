"""Phase 3 Task 12: KMS 信封加密服务单元测试。

覆盖：
    - KMSService 初始化: 禁用模式 / 启用模式 / KEK 加载失败
    - encrypt/decrypt: 加解密一致性 / 不同明文不同密文 / DEK 缓存命中
    - 缓存管理: TTL 过期 / clear_cache / 最大条目数
    - generate_local_kek: 格式 / 长度 / 唯一性
"""
from __future__ import annotations

import base64
import os
import time
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.kms_service import KMSService, generate_local_kek


class TestKMSServiceDisabled:
    """KMS 禁用模式测试。"""

    def test_disabled_by_default(self) -> None:
        """默认配置 KMS_ENABLED=False。"""
        service = KMSService()
        assert service.is_enabled is False

    def test_encrypt_raises_when_disabled(self) -> None:
        """禁用时 encrypt 抛出 RuntimeError。"""
        service = KMSService()
        with pytest.raises(RuntimeError, match="KMS 未启用"):
            service.encrypt(b"data")

    def test_decrypt_raises_when_disabled(self) -> None:
        """禁用时 decrypt 抛出 RuntimeError。"""
        service = KMSService()
        with pytest.raises(RuntimeError, match="KMS 未启用"):
            service.decrypt(b"ciphertext", b"wrapped_dek")


class TestKMSServiceEnabled:
    """KMS 启用模式测试。"""

    @pytest.fixture
    def kms_service(self, monkeypatch) -> KMSService:
        """创建启用了 KMS 的服务实例。"""
        kek = generate_local_kek()
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek)
        return KMSService()

    def test_enabled_when_kek_configured(self, kms_service) -> None:
        """配置 KEK 后 KMS 启用。"""
        assert kms_service.is_enabled is True

    def test_encrypt_decrypt_consistency(self, kms_service) -> None:
        """加密后解密恢复原文。"""
        plaintext = b"sensitive api key 12345"
        ciphertext, wrapped_dek = kms_service.encrypt(plaintext)
        decrypted = kms_service.decrypt(ciphertext, wrapped_dek)
        assert decrypted == plaintext

    def test_different_plaintext_different_ciphertext(self, kms_service) -> None:
        """不同明文产生不同密文（因 DEK 随机）。"""
        ct1, _ = kms_service.encrypt(b"data1")
        ct2, _ = kms_service.encrypt(b"data2")
        assert ct1 != ct2

    def test_same_plaintext_different_ciphertext(self, kms_service) -> None:
        """相同明文每次加密产生不同密文（因 DEK 和 Nonce 随机）。"""
        ct1, _ = kms_service.encrypt(b"same data")
        ct2, _ = kms_service.encrypt(b"same data")
        assert ct1 != ct2

    def test_ciphertext_differs_from_plaintext(self, kms_service) -> None:
        """密文不等于明文。"""
        plaintext = b"secret"
        ciphertext, _ = kms_service.encrypt(plaintext)
        assert ciphertext != plaintext

    def test_decrypt_with_wrong_kek_fails(self, monkeypatch) -> None:
        """使用不同 KEK 解密失败。"""
        kek1 = generate_local_kek()
        kek2 = generate_local_kek()
        monkeypatch.setattr(settings, "KMS_ENABLED", True)

        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek1)
        service1 = KMSService()
        ciphertext, wrapped_dek = service1.encrypt(b"secret")

        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek2)
        service2 = KMSService()
        with pytest.raises(ValueError, match="DEK 解密失败"):
            service2.decrypt(ciphertext, wrapped_dek)

    def test_decrypt_corrupted_data_fails(self, kms_service) -> None:
        """解密损坏的密文失败。"""
        _, wrapped_dek = kms_service.encrypt(b"secret")
        with pytest.raises(ValueError, match="数据解密失败"):
            kms_service.decrypt(b"corrupted_data", wrapped_dek)


class TestDEKCache:
    """DEK 内存缓存测试。"""

    def test_dek_cached_on_decrypt(self, monkeypatch) -> None:
        """解密时 DEK 被缓存，第二次解密复用缓存。"""
        kek = generate_local_kek()
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek)
        service = KMSService()

        ciphertext, wrapped_dek = service.encrypt(b"data")
        # 第一次解密
        service.decrypt(ciphertext, wrapped_dek)
        cache_key = wrapped_dek.hex()
        assert cache_key in service._dek_cache

        # 第二次解密（应复用缓存）
        plaintext = service.decrypt(ciphertext, wrapped_dek)
        assert plaintext == b"data"

    def test_clear_cache(self, monkeypatch) -> None:
        """clear_cache 清空 DEK 缓存。"""
        kek = generate_local_kek()
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek)
        service = KMSService()

        _, wrapped_dek = service.encrypt(b"data")
        service.decrypt(b"data" + b"0" * 8 + wrapped_dek, wrapped_dek) if False else None
        # 直接加密并解密填充缓存
        ct, wd = service.encrypt(b"test")
        service.decrypt(ct, wd)
        assert len(service._dek_cache) > 0

        service.clear_cache()
        assert len(service._dek_cache) == 0

    def test_cache_ttl_expiration(self, monkeypatch) -> None:
        """DEK 缓存 TTL 过期后重新解密 DEK。"""
        kek = generate_local_kek()
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek)
        monkeypatch.setattr(settings, "KMS_DEK_CACHE_TTL", 0)  # TTL=0，立即过期
        service = KMSService()

        ciphertext, wrapped_dek = service.encrypt(b"data")
        service.decrypt(ciphertext, wrapped_dek)

        # 等待一小段时间确保 time.time() > expires_at
        time.sleep(0.01)
        # TTL=0，_get_cached_dek 应返回 None（已过期）
        cache_key = wrapped_dek.hex()
        assert service._get_cached_dek(cache_key) is None

        # 再次解密仍成功（重新解密 DEK）
        plaintext = service.decrypt(ciphertext, wrapped_dek)
        assert plaintext == b"data"


class TestGenerateLocalKek:
    """generate_local_kek 函数测试。"""

    def test_kek_is_base64(self) -> None:
        """KEK 为 Base64 编码字符串。"""
        kek = generate_local_kek()
        decoded = base64.b64decode(kek)
        assert len(decoded) == 32  # AES-256

    def test_kek_uniqueness(self) -> None:
        """连续生成的 KEK 不同。"""
        keks = {generate_local_kek() for _ in range(20)}
        assert len(keks) == 20

    def test_kek_can_be_used_by_service(self, monkeypatch) -> None:
        """生成的 KEK 可被 KMSService 加载使用。"""
        kek = generate_local_kek()
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", kek)
        service = KMSService()
        assert service.is_enabled is True


class TestKEKLoading:
    """KEK 加载测试。"""

    def test_no_kek_configured_disables_kms(self, monkeypatch) -> None:
        """未配置 KEK 时 KMS 自动禁用。"""
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", "")
        service = KMSService()
        assert service.is_enabled is False

    def test_invalid_base64_kek_disables_kms(self, monkeypatch) -> None:
        """无效 Base64 KEK 时 KMS 自动禁用。"""
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", "not-valid-base64!!!")
        service = KMSService()
        assert service.is_enabled is False

    def test_wrong_length_kek_disables_kms(self, monkeypatch) -> None:
        """KEK 长度不正确时 KMS 自动禁用。"""
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        # 16 字节而非 32 字节
        short_kek = base64.b64encode(os.urandom(16)).decode("ascii")
        monkeypatch.setattr(settings, "KMS_LOCAL_KEK", short_kek)
        service = KMSService()
        assert service.is_enabled is False

    def test_unknown_kek_source_disables_kms(self, monkeypatch) -> None:
        """未知 KEK 来源时 KMS 自动禁用。"""
        monkeypatch.setattr(settings, "KMS_ENABLED", True)
        monkeypatch.setattr(settings, "KMS_KEK_SOURCE", "unknown")
        service = KMSService()
        assert service.is_enabled is False
