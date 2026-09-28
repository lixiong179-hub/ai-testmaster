"""Phase 3 Task 12: KMS 信封加密服务。

核心概念：
    - KEK（Key Encryption Key）  : 主密钥，加密 DEK，来源为本地/AWS KMS
    - DEK（Data Encryption Key） : 数据加密密钥，加密实际数据，使用后即弃
    - 信封加密流程：
        加密：生成随机 DEK → 用 DEK 加密数据 → 用 KEK 加密 DEK → 存储 (密文, 加密后的 DEK)
        解密：用 KEK 解密 DEK → 用 DEK 解密数据

设计要点：
    - DEK 内存缓存（短 TTL），避免每次解密都重新解密 DEK
    - AES-256-GCM 对称加密（同时提供机密性与完整性）
    - 本地 KEK 通过 Base64 编码 32 字节密钥配置
    - 开发环境可关闭（KMS_ENABLED=False），数据明文存储

使用方式：
    service = KMSService()
    # 加密
    encrypted, wrapped_dek = service.encrypt(b"sensitive data")
    # 解密
    plaintext = service.decrypt(encrypted, wrapped_dek)

依赖：
    cryptography==46.0.6（已在 requirements.txt 中）
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

from app.core.config import settings

# AES-256 密钥长度（字节）
_KEY_LENGTH: int = 32
# GCM Nonce 长度（字节）
_NONCE_LENGTH: int = 12
# DEK 缓存最大条目数
_MAX_CACHE_SIZE: int = 100


@dataclass
class _DEKCacheEntry:
    """DEK 缓存条目。

    Attributes:
        dek: 解密后的 DEK 字节流
        expires_at: 过期时间戳
    """

    dek: bytes
    expires_at: float


class KMSService:
    """KMS 信封加密服务。

    提供 encrypt/decrypt 接口，内部实现 DEK 生成、KEK 包裹、内存缓存。

    使用方式：
        service = KMSService()
        if service.is_enabled:
            encrypted, wrapped_dek = service.encrypt(b"sensitive data")
            # 存储 encrypted 和 wrapped_dek
            plaintext = service.decrypt(encrypted, wrapped_dek)
    """

    def __init__(self) -> None:
        """初始化 KMS 服务，加载 KEK。"""
        self._enabled: bool = settings.KMS_ENABLED
        self._kek: Optional[bytes] = None
        self._dek_cache: Dict[str, _DEKCacheEntry] = {}
        self._cache_ttl: int = settings.KMS_DEK_CACHE_TTL

        if self._enabled:
            self._kek = self._load_kek()
            if self._kek is None:
                logger.warning(
                    "[KMS] KEK 加载失败，信封加密降级为禁用模式。"
                    "生产环境必须配置 KMS_LOCAL_KEK。"
                )
                self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """KMS 是否已启用。"""
        return self._enabled

    def _load_kek(self) -> Optional[bytes]:
        """加载 KEK（主密钥）。

        根据 KMS_KEK_SOURCE 选择加载方式：
            - local: 从 KMS_LOCAL_KEK 环境变量加载 Base64 编码密钥
            - aws-kms: 调用 AWS KMS API（后续扩展，当前未实现）

        Returns:
            Optional[bytes]: 32 字节 KEK，加载失败返回 None
        """
        source = settings.KMS_KEK_SOURCE
        if source == "local":
            kek_b64 = settings.KMS_LOCAL_KEK
            if not kek_b64:
                return None
            try:
                kek = base64.b64decode(kek_b64)
                if len(kek) != _KEY_LENGTH:
                    logger.error(
                        f"[KMS] KEK 长度不正确: 期望 {_KEY_LENGTH} 字节, 实际 {len(kek)} 字节"
                    )
                    return None
                return kek
            except Exception as e:
                logger.error(f"[KMS] KEK Base64 解码失败: {e}")
                return None
        elif source == "aws-kms":
            logger.warning("[KMS] AWS KMS 尚未实现，降级为本地 KEK")
            return None
        else:
            logger.error(f"[KMS] 未知 KEK 来源: {source}")
            return None

    def encrypt(self, plaintext: bytes) -> Tuple[bytes, bytes]:
        """信封加密：生成 DEK → 用 DEK 加密数据 → 用 KEK 加密 DEK。

        Args:
            plaintext: 待加密的明文数据

        Returns:
            Tuple[bytes, bytes]: (加密后的密文, KEK 加密后的 DEK)
                - 密文格式: nonce(12B) || ciphertext || tag(16B)
                - wrapped_dek 格式: nonce(12B) || encrypted_dek || tag(16B)

        Raises:
            RuntimeError: KMS 未启用
        """
        if not self._enabled or self._kek is None:
            raise RuntimeError("KMS 未启用，无法加密")

        # 1. 生成随机 DEK
        dek = os.urandom(_KEY_LENGTH)

        # 2. 用 DEK 加密数据（AES-256-GCM）
        data_nonce = os.urandom(_NONCE_LENGTH)
        aesgcm_dek = AESGCM(dek)
        ciphertext = data_nonce + aesgcm_dek.encrypt(data_nonce, plaintext, None)

        # 3. 用 KEK 加密 DEK
        kek_nonce = os.urandom(_NONCE_LENGTH)
        aesgcm_kek = AESGCM(self._kek)
        wrapped_dek = kek_nonce + aesgcm_kek.encrypt(kek_nonce, dek, None)

        return ciphertext, wrapped_dek

    def decrypt(self, ciphertext: bytes, wrapped_dek: bytes) -> bytes:
        """信封解密：用 KEK 解密 DEK → 用 DEK 解密数据。

        DEK 内存缓存：相同 wrapped_dek 的 DEK 在 TTL 内复用，避免重复解密。

        Args:
            ciphertext: encrypt 返回的密文
            wrapped_dek: encrypt 返回的 KEK 加密后的 DEK

        Returns:
            bytes: 解密后的明文

        Raises:
            RuntimeError: KMS 未启用
            ValueError: 解密失败（密钥不匹配或数据损坏）
        """
        if not self._enabled or self._kek is None:
            raise RuntimeError("KMS 未启用，无法解密")

        # 1. 解密 DEK（优先从缓存读取）
        cache_key = wrapped_dek.hex()
        dek = self._get_cached_dek(cache_key)
        if dek is None:
            try:
                kek_nonce = wrapped_dek[:_NONCE_LENGTH]
                encrypted_dek = wrapped_dek[_NONCE_LENGTH:]
                aesgcm_kek = AESGCM(self._kek)
                dek = aesgcm_kek.decrypt(kek_nonce, encrypted_dek, None)
                self._cache_dek(cache_key, dek)
            except Exception as e:
                raise ValueError(f"DEK 解密失败: {e}") from e

        # 2. 用 DEK 解密数据
        try:
            data_nonce = ciphertext[:_NONCE_LENGTH]
            encrypted_data = ciphertext[_NONCE_LENGTH:]
            aesgcm_dek = AESGCM(dek)
            return aesgcm_dek.decrypt(data_nonce, encrypted_data, None)
        except Exception as e:
            raise ValueError(f"数据解密失败: {e}") from e

    def _get_cached_dek(self, cache_key: str) -> Optional[bytes]:
        """从缓存读取 DEK。

        Args:
            cache_key: wrapped_dek 的十六进制字符串

        Returns:
            Optional[bytes]: 缓存的 DEK，未命中或已过期返回 None
        """
        entry = self._dek_cache.get(cache_key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            # 过期，移除
            self._dek_cache.pop(cache_key, None)
            return None
        return entry.dek

    def _cache_dek(self, cache_key: str, dek: bytes) -> None:
        """缓存 DEK。

        超过最大缓存条目数时清空全部缓存（简单 LRU 替代）。

        Args:
            cache_key: wrapped_dek 的十六进制字符串
            dek: 解密后的 DEK
        """
        if len(self._dek_cache) >= _MAX_CACHE_SIZE:
            self._dek_cache.clear()
        self._dek_cache[cache_key] = _DEKCacheEntry(
            dek=dek,
            expires_at=time.time() + self._cache_ttl,
        )

    def clear_cache(self) -> None:
        """清空 DEK 缓存（用于密钥轮换等场景）。"""
        self._dek_cache.clear()
        logger.info("[KMS] DEK 缓存已清空")


def generate_local_kek() -> str:
    """生成本地 KEK 密钥（Base64 编码 32 字节）。

    用于生成生产环境 KMS_LOCAL_KEK 配置值。

    Returns:
        str: Base64 编码的 AES-256 密钥
    """
    kek = os.urandom(_KEY_LENGTH)
    return base64.b64encode(kek).decode("ascii")


__all__ = ["KMSService", "generate_local_kek"]
