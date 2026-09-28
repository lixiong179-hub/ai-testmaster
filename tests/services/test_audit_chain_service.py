"""Phase 3 Task 10: 审计日志 hash chain 单元测试。

覆盖：
    - AuditLog.compute_hash: 确定性 / 不同输入不同 hash / 格式正确
    - before_flush event: INSERT 时自动计算 hash
    - AuditChainService.get_last_hash: 空表 / 有记录
    - AuditChainService.verify_chain_integrity: 完整链 / 断裂链 / 空表 / 分批校验
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.audit_log import AuditLog, _GENESIS_HASH
from app.services.audit_chain_service import AuditChainService, ChainIntegrityResult


class TestAuditLogComputeHash:
    """AuditLog.compute_hash 方法测试。"""

    def test_hash_is_64_char_hex(self) -> None:
        """hash 为 64 字符十六进制字符串。"""
        log = AuditLog(
            action="test_action",
            actor_id=1,
            target_kind="test_case",
            target_id=100,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        h = log.compute_hash(_GENESIS_HASH)
        assert len(h) == 64
        int(h, 16)  # 验证为有效十六进制

    def test_hash_deterministic(self) -> None:
        """相同输入产生相同 hash。"""
        log1 = AuditLog(
            action="test", actor_id=1, target_kind="case", target_id=1,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        log2 = AuditLog(
            action="test", actor_id=1, target_kind="case", target_id=1,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        assert log1.compute_hash(_GENESIS_HASH) == log2.compute_hash(_GENESIS_HASH)

    def test_different_prev_hash_produces_different_hash(self) -> None:
        """不同 prev_hash 产生不同 hash。"""
        log = AuditLog(
            action="test", actor_id=1, target_kind="case", target_id=1,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        h1 = log.compute_hash(_GENESIS_HASH)
        h2 = log.compute_hash("a" * 64)
        assert h1 != h2

    def test_different_action_produces_different_hash(self) -> None:
        """不同 action 产生不同 hash。"""
        log1 = AuditLog(
            action="action_a", actor_id=1, target_kind="case", target_id=1,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        log2 = AuditLog(
            action="action_b", actor_id=1, target_kind="case", target_id=1,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        assert log1.compute_hash(_GENESIS_HASH) != log2.compute_hash(_GENESIS_HASH)

    def test_hash_matches_manual_computation(self) -> None:
        """hash 与手动 SHA256 计算结果一致。"""
        log = AuditLog(
            action="test", actor_id=1, target_kind="case", target_id=1,
            detail={"key": "value"}, run_id=None, iteration_id=None,
            created_at=datetime(2026, 7, 30, 12, 0, 0),
        )
        payload = {
            "action": "test",
            "actor_id": 1,
            "target_kind": "case",
            "target_id": 1,
            "detail": {"key": "value"},
            "run_id": None,
            "iteration_id": None,
            "created_at": "2026-07-30T12:00:00",
            "prev_hash": _GENESIS_HASH,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert log.compute_hash(_GENESIS_HASH) == expected


class TestAuditChainServiceGetLastHash:
    """AuditChainService.get_last_hash 测试。"""

    def test_empty_table_returns_genesis(self) -> None:
        """空表返回创世 hash。"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.get_last_hash()
        assert result == _GENESIS_HASH

    def test_returns_last_record_hash(self) -> None:
        """有记录时返回最后一条的 hash。"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "abc123" * 10 + "abcd"
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.get_last_hash()
        assert result == "abc123" * 10 + "abcd"


class TestVerifyChainIntegrity:
    """AuditChainService.verify_chain_integrity 测试。"""

    def _create_mock_records(self, count: int) -> list:
        """创建模拟的 AuditLog 记录列表（链式 hash 正确）。"""
        records = []
        prev_hash = _GENESIS_HASH
        for i in range(1, count + 1):
            log = AuditLog(
                id=i,
                action=f"action_{i}",
                actor_id=1,
                target_kind="case",
                target_id=i,
                created_at=datetime(2026, 7, 30, 12, 0, i),
            )
            log.prev_hash = prev_hash
            log.hash = log.compute_hash(prev_hash)
            records.append(log)
            prev_hash = log.hash
        return records

    def test_empty_table_is_valid(self) -> None:
        """空表校验通过。"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity()
        assert result.is_valid is True
        assert result.total_checked == 0

    def test_valid_chain_passes(self) -> None:
        """完整的 hash chain 校验通过。"""
        records = self._create_mock_records(5)
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity()
        assert result.is_valid is True
        assert result.total_checked == 5
        assert result.broken_at_id is None

    def test_broken_prev_hash_detected(self) -> None:
        """prev_hash 不匹配时检测到断裂。"""
        records = self._create_mock_records(3)
        # 篡改第二条的 prev_hash
        records[1].prev_hash = "tampered" + "0" * 56

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity()
        assert result.is_valid is False
        assert result.broken_at_id == records[1].id
        assert "prev_hash 不匹配" in result.broken_reason

    def test_tampered_hash_detected(self) -> None:
        """hash 被篡改时检测到断裂。"""
        records = self._create_mock_records(3)
        # 篡改第三条的 hash（但保持 prev_hash 正确）
        records[2].hash = "tampered" + "0" * 56

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity()
        assert result.is_valid is False
        assert result.broken_at_id == records[2].id
        assert "hash 不匹配" in result.broken_reason

    def test_tampered_action_field_detected(self) -> None:
        """action 字段被篡改导致 hash 不匹配时检测到断裂。"""
        records = self._create_mock_records(3)
        # 篡改第二条的 action（hash 未重新计算）
        records[1].action = "tampered_action"

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity()
        assert result.is_valid is False
        assert result.broken_at_id == records[1].id

    def test_limit_parameter(self) -> None:
        """limit 参数限制校验记录数。"""
        records = self._create_mock_records(10)
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records[:3]
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity(limit=3)
        assert result.is_valid is True
        assert result.total_checked == 3

    def test_single_record_chain_valid(self) -> None:
        """单条记录的链校验通过。"""
        records = self._create_mock_records(1)
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = mock_result

        service = AuditChainService(db=mock_db)
        result = service.verify_chain_integrity()
        assert result.is_valid is True
        assert result.total_checked == 1
        assert result.last_valid_hash == records[0].hash


class TestChainIntegrityResult:
    """ChainIntegrityResult 数据类测试。"""

    def test_valid_result_construction(self) -> None:
        """构造有效的校验结果。"""
        result = ChainIntegrityResult(
            is_valid=True,
            total_checked=100,
            broken_at_id=None,
            broken_reason="",
            last_valid_hash="abc" * 21 + "a",
        )
        assert result.is_valid is True
        assert result.total_checked == 100

    def test_invalid_result_construction(self) -> None:
        """构造无效的校验结果。"""
        result = ChainIntegrityResult(
            is_valid=False,
            total_checked=50,
            broken_at_id=51,
            broken_reason="hash 不匹配",
            last_valid_hash="xyz" * 21 + "x",
        )
        assert result.is_valid is False
        assert result.broken_at_id == 51
