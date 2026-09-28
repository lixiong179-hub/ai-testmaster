"""JWT RSA 密钥对管理模块（add-security-compliance Task 1.3）。

提供 RSA 私钥/公钥的加载、缓存与降级策略：

加载优先级（高 → 低）：
    1. settings.JWT_PRIVATE_KEY / JWT_PUBLIC_KEY（直接 PEM 字符串，KMS 注入）
    2. settings.JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH（PEM 文件路径）
    3. 本地缓存文件 .secret_keys 中的 jwt_private_key / jwt_public_key
    4. 开发/测试环境自动生成 RSA-2048 密钥对并持久化到缓存文件
    5. 生产环境若未配置 RSA 密钥对，回退到 HS256（JWT_SECRET_KEY）并记录 WARNING

设计要点：
    - 密钥值本身不记录日志，仅记录来源与长度
    - 自动生成的密钥对写入 .secret_keys 缓存文件，权限 0o600
    - 生产环境强制要求显式配置 RSA 密钥对，不自动生成（避免弱密钥）
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings
from app.core.key_management import (
    BASE_DIR,
    _log_key_source,
    load_cached_key,
    save_cached_key,
)

_logger = logging.getLogger(__name__)

# RSA 密钥缓存文件（与 .secret_keys 共享，避免新增文件）
_KEY_CACHE_FILE: Path = BASE_DIR / ".secret_keys"

# 内存缓存：避免每次 JWT 签名/验签都重新加载 PEM
_cached_private_key: Optional[str] = None
_cached_public_key: Optional[str] = None


def _generate_rsa_keypair() -> Tuple[str, str]:
    """生成 RSA-2048 密钥对，返回 PEM 格式 (private_pem, public_pem)。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _load_key_from_path(path: str) -> str:
    """从文件路径加载 PEM 字符串。文件不存在或读取失败返回空字符串。"""
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception as e:
        _logger.warning(f"从路径 {path} 加载密钥失败: {e}")
        return ""


def get_jwt_private_key() -> str:
    """获取 JWT RSA 私钥（PEM 格式）。

    返回空字符串表示未配置 RSA 私钥，调用方应回退到 HS256。
    生产环境未配置时记录 WARNING 但不抛异常，由 ensure_secret_keys 统一处理。
    """
    global _cached_private_key
    if _cached_private_key is not None:
        return _cached_private_key

    # 1. 优先使用环境变量直接配置的 PEM 字符串
    if settings.JWT_PRIVATE_KEY:
        _log_key_source("JWT_PRIVATE_KEY", "env")
        _cached_private_key = settings.JWT_PRIVATE_KEY
        return _cached_private_key

    # 2. 通过文件路径加载
    if settings.JWT_PRIVATE_KEY_PATH:
        key = _load_key_from_path(settings.JWT_PRIVATE_KEY_PATH)
        if key:
            _log_key_source("JWT_PRIVATE_KEY", "path")
            _cached_private_key = key
            return _cached_private_key

    # 3. 从缓存文件加载
    key = load_cached_key("jwt_private_key", _KEY_CACHE_FILE)
    if key:
        _log_key_source("JWT_PRIVATE_KEY", "cache")
        _cached_private_key = key
        return _cached_private_key

    # 4. 开发/测试环境自动生成
    if settings.ENVIRONMENT != "prod":
        private_pem, _ = _generate_rsa_keypair()
        save_cached_key("jwt_private_key", private_pem, _KEY_CACHE_FILE)
        _log_key_source("JWT_PRIVATE_KEY", "auto-generated", auto_generated=True)
        _cached_private_key = private_pem
        return _cached_private_key

    # 5. 生产环境未配置：记录 WARNING，调用方回退到 HS256
    _logger.warning(
        "[KEY_AUDIT] key=JWT_PRIVATE_KEY source=missing "
        "回退到 HS256 算法（迁移期兼容），生产环境必须配置 RSA 私钥"
    )
    _cached_private_key = ""
    return _cached_private_key


def get_jwt_public_key() -> str:
    """获取 JWT RSA 公钥（PEM 格式）。

    返回空字符串表示未配置 RSA 公钥，调用方应回退到 HS256。
    """
    global _cached_public_key
    if _cached_public_key is not None:
        return _cached_public_key

    # 1. 优先使用环境变量直接配置的 PEM 字符串
    if settings.JWT_PUBLIC_KEY:
        _log_key_source("JWT_PUBLIC_KEY", "env")
        _cached_public_key = settings.JWT_PUBLIC_KEY
        return _cached_public_key

    # 2. 通过文件路径加载
    if settings.JWT_PUBLIC_KEY_PATH:
        key = _load_key_from_path(settings.JWT_PUBLIC_KEY_PATH)
        if key:
            _log_key_source("JWT_PUBLIC_KEY", "path")
            _cached_public_key = key
            return _cached_public_key

    # 3. 从缓存文件加载
    key = load_cached_key("jwt_public_key", _KEY_CACHE_FILE)
    if key:
        _log_key_source("JWT_PUBLIC_KEY", "cache")
        _cached_public_key = key
        return _cached_public_key

    # 4. 开发/测试环境自动生成（与私钥配对）
    if settings.ENVIRONMENT != "prod":
        # 若私钥已生成则派生公钥；否则同时生成
        private_pem = get_jwt_private_key()
        if private_pem:
            try:
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.serialization import load_pem_private_key

                private_key_obj = load_pem_private_key(
                    private_pem.encode("utf-8"), password=None
                )
                public_pem = private_key_obj.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ).decode("utf-8")
                save_cached_key("jwt_public_key", public_pem, _KEY_CACHE_FILE)
                _log_key_source("JWT_PUBLIC_KEY", "auto-generated", auto_generated=True)
                _cached_public_key = public_pem
                return _cached_public_key
            except Exception as e:
                _logger.warning(f"从私钥派生公钥失败，重新生成密钥对: {e}")
                # 私钥可能损坏，重置缓存后重新生成
                global _cached_private_key
                _cached_private_key = None
                # 清除缓存文件中的旧密钥
                try:
                    cache = json.loads(_KEY_CACHE_FILE.read_text())
                    cache.pop("jwt_private_key", None)
                    cache.pop("jwt_public_key", None)
                    _KEY_CACHE_FILE.write_text(json.dumps(cache))
                except Exception as e:
                    _logger.debug(f"清除缓存文件旧密钥失败（非致命）: {e}")
        # 重新生成密钥对
        private_pem, public_pem = _generate_rsa_keypair()
        save_cached_key("jwt_private_key", private_pem, _KEY_CACHE_FILE)
        save_cached_key("jwt_public_key", public_pem, _KEY_CACHE_FILE)
        _log_key_source("JWT_PRIVATE_KEY", "auto-generated", auto_generated=True)
        _log_key_source("JWT_PUBLIC_KEY", "auto-generated", auto_generated=True)
        _cached_private_key = private_pem
        _cached_public_key = public_pem
        return _cached_public_key

    # 5. 生产环境未配置
    _logger.warning(
        "[KEY_AUDIT] key=JWT_PUBLIC_KEY source=missing "
        "回退到 HS256 算法（迁移期兼容），生产环境必须配置 RSA 公钥"
    )
    _cached_public_key = ""
    return _cached_public_key


def reset_cache() -> None:
    """重置内存缓存（仅供测试使用，避免跨测试污染）。"""
    global _cached_private_key, _cached_public_key
    _cached_private_key = None
    _cached_public_key = None
