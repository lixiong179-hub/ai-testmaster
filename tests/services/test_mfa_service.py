"""Phase 3 Task 3: MFA 多因子认证服务单元测试。

覆盖：
    - MFAService.generate_totp_secret: Base32 格式 / 唯一性
    - MFAService.get_totp_uri: otpauth URI 格式
    - MFAService.verify_totp_code: 正确码 / 错误码 / 空值 / 时间窗口
    - MFAService.generate_backup_codes: 数量 / 唯一性 / 哈希与明文不同
    - MFAService.verify_and_consume_backup_code: 正确消费 / 错误码 / 一次性消费
"""
from __future__ import annotations

import pytest

# R4-4：pyotp 未安装时整文件 skip，而非 fail —— 属环境依赖缺失，非代码缺陷
pytest.importorskip("pyotp", reason="环境未安装 pyotp，非代码缺陷")

import pyotp  # noqa: E402  (需置于 importorskip 之后)

from app.services.mfa_service import MFAService


class TestGenerateTotpSecret:
    """TOTP 密钥生成测试。"""

    def test_secret_is_base32(self) -> None:
        """密钥为 Base32 格式（32 字符，A-Z2-7）。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        assert isinstance(secret, str)
        assert len(secret) == 32
        # Base32 字符集：A-Z + 2-7
        for char in secret:
            assert char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

    def test_secret_uniqueness(self) -> None:
        """连续生成的密钥不同。"""
        service = MFAService()
        secrets = {service.generate_totp_secret() for _ in range(50)}
        assert len(secrets) == 50


class TestGetTotpUri:
    """otpauth URI 生成测试。"""

    def test_uri_format(self) -> None:
        """URI 包含 otpauth:// 前缀和 totp 方法。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        uri = service.get_totp_uri(secret=secret, account="user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "user%40example.com" in uri or "user@example.com" in uri

    def test_uri_contains_issuer(self) -> None:
        """URI 包含 issuer 参数。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        uri = service.get_totp_uri(
            secret=secret, account="user@example.com", issuer="TestApp"
        )
        assert "issuer=TestApp" in uri

    def test_uri_contains_secret(self) -> None:
        """URI 包含 secret 参数。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        uri = service.get_totp_uri(secret=secret, account="user@example.com")
        assert f"secret={secret}" in uri


class TestVerifyTotpCode:
    """TOTP 动态码校验测试。"""

    def test_valid_code_passes(self) -> None:
        """当前 TOTP 码校验通过。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert service.verify_totp_code(secret=secret, code=code) is True

    def test_invalid_code_fails(self) -> None:
        """错误码校验失败。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        assert service.verify_totp_code(secret=secret, code="000000") is False

    def test_empty_secret_fails(self) -> None:
        """空密钥校验失败。"""
        service = MFAService()
        assert service.verify_totp_code(secret="", code="123456") is False

    def test_empty_code_fails(self) -> None:
        """空码校验失败。"""
        service = MFAService()
        secret = service.generate_totp_secret()
        assert service.verify_totp_code(secret=secret, code="") is False

    def test_none_secret_fails(self) -> None:
        """None 密钥校验失败。"""
        service = MFAService()
        assert service.verify_totp_code(secret=None, code="123456") is False  # type: ignore[arg-type]

    def test_valid_window_allows_drift(self) -> None:
        """valid_window=1 允许 ±30s 时间漂移。"""
        import time

        service = MFAService()
        secret = service.generate_totp_secret()
        totp = pyotp.TOTP(secret)
        # 获取上一时间窗口的码
        code = totp.at(time.time() - 30)
        assert service.verify_totp_code(secret=secret, code=code, valid_window=1) is True


class TestGenerateBackupCodes:
    """备份码生成测试。"""

    def test_code_count(self) -> None:
        """生成 10 个备份码。"""
        service = MFAService()
        plaintext, hashed = service.generate_backup_codes()
        assert len(plaintext) == 10
        assert len(hashed) == 10

    def test_code_length(self) -> None:
        """每个备份码长度为 8。"""
        service = MFAService()
        plaintext, _ = service.generate_backup_codes()
        for code in plaintext:
            assert len(code) == 8

    def test_code_uniqueness(self) -> None:
        """备份码互不相同。"""
        service = MFAService()
        plaintext, _ = service.generate_backup_codes()
        assert len(set(plaintext)) == 10

    def test_hashed_different_from_plaintext(self) -> None:
        """哈希值与明文不同。"""
        service = MFAService()
        plaintext, hashed = service.generate_backup_codes()
        for plain, hash_val in zip(plaintext, hashed):
            assert plain != hash_val
            assert hash_val.startswith("$2")  # bcrypt 前缀

    def test_code_alphabet_excludes_confusing_chars(self) -> None:
        """备份码不含易混淆字符 0/O/1/I/L。"""
        service = MFAService()
        plaintext, _ = service.generate_backup_codes()
        confusing = set("01OIL")
        for code in plaintext:
            assert not (set(code) & confusing)


class TestVerifyAndConsumeBackupCode:
    """备份码校验与消费测试。"""

    def test_valid_backup_code_consumed(self) -> None:
        """正确的备份码校验通过并被消费。"""
        service = MFAService()
        plaintext, hashed = service.generate_backup_codes()
        verified, remaining = service.verify_and_consume_backup_code(
            stored_hashed_codes=hashed,
            submitted_code=plaintext[0],
        )
        assert verified is True
        assert len(remaining) == 9  # 消费一个后剩 9 个

    def test_invalid_backup_code_not_consumed(self) -> None:
        """错误的备份码校验失败，列表不变。"""
        service = MFAService()
        _, hashed = service.generate_backup_codes()
        verified, remaining = service.verify_and_consume_backup_code(
            stored_hashed_codes=hashed,
            submitted_code="WRONGCODE",
        )
        assert verified is False
        assert len(remaining) == 10  # 列表不变

    def test_backup_code_one_time_use(self) -> None:
        """备份码一次性使用：第二次使用同一码校验失败。"""
        service = MFAService()
        plaintext, hashed = service.generate_backup_codes()

        # 第一次使用成功
        verified1, remaining1 = service.verify_and_consume_backup_code(
            stored_hashed_codes=hashed,
            submitted_code=plaintext[3],
        )
        assert verified1 is True
        assert len(remaining1) == 9

        # 第二次使用同一码失败（已从列表移除）
        verified2, remaining2 = service.verify_and_consume_backup_code(
            stored_hashed_codes=remaining1,
            submitted_code=plaintext[3],
        )
        assert verified2 is False
        assert len(remaining2) == 9

    def test_empty_stored_codes_fails(self) -> None:
        """空备份码列表校验失败。"""
        service = MFAService()
        verified, remaining = service.verify_and_consume_backup_code(
            stored_hashed_codes=[],
            submitted_code="ANYCODE",
        )
        assert verified is False
        assert remaining == []

    def test_empty_submitted_code_fails(self) -> None:
        """空提交码校验失败。"""
        service = MFAService()
        _, hashed = service.generate_backup_codes()
        verified, remaining = service.verify_and_consume_backup_code(
            stored_hashed_codes=hashed,
            submitted_code="",
        )
        assert verified is False
        assert len(remaining) == 10

    def test_consume_all_codes(self) -> None:
        """连续消费所有备份码后列表为空。"""
        service = MFAService()
        plaintext, hashed = service.generate_backup_codes()
        remaining = hashed
        for code in plaintext:
            verified, remaining = service.verify_and_consume_backup_code(
                stored_hashed_codes=remaining,
                submitted_code=code,
            )
            assert verified is True
        assert len(remaining) == 0
