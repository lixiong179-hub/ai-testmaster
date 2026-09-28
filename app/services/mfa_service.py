"""Phase 3 Task 3: MFA 多因子认证服务。

核心能力：
    - generate_totp_secret   : 生成 Base32 TOTP 密钥
    - get_totp_uri           : 构造 otpauth:// URI（供 QR 码扫描）
    - verify_totp_code       : 校验 6 位 TOTP 动态码（含 ±1 时间窗口容差）
    - generate_backup_codes  : 生成 10 个一次性备份码（bcrypt 哈希存储）
    - verify_backup_code     : 校验并消费备份码（一次性，使用后从列表移除）

设计原则：
    - TOTP 密钥仅在 setup 阶段返回明文一次，后续仅存哈希
    - 备份码使用 bcrypt 哈希存储，明文仅返回一次
    - 时间窗口容差 ±1（共 3 个 30s 窗口），平衡安全与用户体验
    - 密钥生成使用 secrets 模块，确保密码学安全

依赖：
    pip install pyotp==2.9.0 qrcode==7.4.2
"""
from __future__ import annotations

import json
import secrets
from typing import List, Optional, Tuple

import pyotp
from loguru import logger
from passlib.context import CryptContext

from app.core.config import settings

# 备份码 bcrypt 哈希上下文（复用 passlib，与密码哈希一致）
_backup_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 备份码数量与格式
_BACKUP_CODE_COUNT: int = 10
_BACKUP_CODE_LENGTH: int = 8  # 8 位字母数字


class MFAService:
    """MFA 多因子认证服务。

    提供 TOTP 密钥管理、动态码校验、备份码生成与消费能力。
    无状态设计，所有数据持久化由调用方负责（User 模型字段）。

    使用方式：
        service = MFAService()
        # 设置阶段
        secret = service.generate_totp_secret()
        uri = service.get_totp_uri(secret=secret, account="user@example.com")
        # 校验阶段
        if service.verify_totp_code(secret=secret, code="123456"):
            # 启用 MFA
            ...
        # 备份码
        plaintext_codes, hashed_codes = service.generate_backup_codes()
    """

    def generate_totp_secret(self) -> str:
        """生成 Base32 编码的 TOTP 密钥。

        Returns:
            str: 32 字符的 Base32 密钥（兼容 Google Authenticator）
        """
        return pyotp.random_base32()

    def get_totp_uri(
        self,
        *,
        secret: str,
        account: str,
        issuer: Optional[str] = None,
    ) -> str:
        """构造 otpauth:// URI（供 QR 码扫描）。

        Args:
            secret: Base32 TOTP 密钥
            account: 用户账号（通常为邮箱或用户名）
            issuer: 发行方名称（默认使用 APP_NAME）

        Returns:
            str: otpauth://totp/... 格式的 URI
        """
        issuer_name = issuer or settings.APP_NAME
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=account, issuer_name=issuer_name)

    def verify_totp_code(
        self,
        *,
        secret: str,
        code: str,
        valid_window: int = 1,
    ) -> bool:
        """校验 6 位 TOTP 动态码。

        Args:
            secret: Base32 TOTP 密钥
            code: 用户输入的 6 位动态码
            valid_window: 时间窗口容差（±N 个 30s 窗口），默认 1

        Returns:
            bool: True 表示校验通过
        """
        if not secret or not code:
            return False
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=valid_window)
        except Exception as e:
            logger.warning(f"[MFA] TOTP 校验异常: {e}")
            return False

    def generate_backup_codes(self) -> Tuple[List[str], List[str]]:
        """生成一次性备份码。

        生成 10 个 8 位字母数字备份码，返回明文列表与 bcrypt 哈希列表。
        明文列表仅返回一次，调用方应展示给用户保存；哈希列表持久化到 User.mfa_backup_codes。

        Returns:
            Tuple[List[str], List[str]]: (明文备份码列表, bcrypt 哈希列表)
        """
        plaintext_codes: List[str] = []
        hashed_codes: List[str] = []
        for _ in range(_BACKUP_CODE_COUNT):
            # 8 位字母数字（大写，去除易混淆字符 0/O/1/I/L）
            alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
            code = "".join(secrets.choice(alphabet) for _ in range(_BACKUP_CODE_LENGTH))
            plaintext_codes.append(code)
            hashed_codes.append(_backup_pwd_context.hash(code))
        return plaintext_codes, hashed_codes

    def verify_and_consume_backup_code(
        self,
        *,
        stored_hashed_codes: List[str],
        submitted_code: str,
    ) -> Tuple[bool, List[str]]:
        """校验并消费备份码（一次性）。

        遍历已存储的哈希备份码，找到匹配项后从列表中移除（一次性使用）。

        Args:
            stored_hashed_codes: 数据库中存储的哈希备份码列表
            submitted_code: 用户提交的备份码

        Returns:
            Tuple[bool, List[str]]: (是否校验通过, 消费后的剩余哈希列表)
        """
        if not stored_hashed_codes or not submitted_code:
            return False, stored_hashed_codes or []

        for idx, hashed_code in enumerate(stored_hashed_codes):
            try:
                if _backup_pwd_context.verify(submitted_code, hashed_code):
                    # 匹配，移除已使用的备份码
                    remaining = stored_hashed_codes[:idx] + stored_hashed_codes[idx + 1:]
                    logger.info("[MFA] 备份码已消费，剩余数量=%d", len(remaining))
                    return True, remaining
            except Exception as e:
                logger.warning(f"[MFA] 备份码校验异常: {e}")
                continue
        return False, stored_hashed_codes


__all__ = ["MFAService"]
