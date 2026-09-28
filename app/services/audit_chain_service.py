"""Phase 3 Task 10: 审计日志 hash chain 完整性校验服务。

核心能力：
    - verify_chain_integrity : 按 id 顺序遍历审计日志，重算每条 hash 并校验链式完整性
    - get_last_hash          : 获取最后一条审计日志的 hash（供新记录设置 prev_hash）
    - compute_record_hash    : 静态方法，计算单条记录的 hash

设计原则：
    - 校验时按 id 顺序遍历，逐条重算 hash 并与存储值比对
    - prev_hash 必须等于上一条记录的 hash
    - 任一记录被篡改（action/actor_id/target_kind 等字段被修改）都会导致 hash 不匹配
    - 性能：校验全量审计日志可能较慢，支持 limit/offset 分批校验

使用场景：
    - 定期完整性校验（定时任务每日执行）
    - SOC2 审计前完整性验证
    - 安全事件后取证验证
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog, _GENESIS_HASH


@dataclass
class ChainIntegrityResult:
    """hash chain 完整性校验结果。

    Attributes:
        is_valid         : 整条链是否完整有效
        total_checked    : 校验的记录总数
        broken_at_id     : 首个断裂点的记录 ID（None 表示无断裂）
        broken_reason    : 断裂原因描述
        last_valid_hash  : 最后一条有效记录的 hash
    """

    is_valid: bool
    total_checked: int
    broken_at_id: Optional[int]
    broken_reason: str
    last_valid_hash: str


class AuditChainService:
    """审计日志 hash chain 完整性校验服务。

    使用方式：
        service = AuditChainService(db=session)
        result = service.verify_chain_integrity()
        if not result.is_valid:
            logger.error(f"审计日志链断裂: id={result.broken_at_id} reason={result.broken_reason}")
    """

    def __init__(self, db: Session) -> None:
        """注入数据库会话。

        Args:
            db: 同步数据库会话（审计校验通常在后台任务中执行）
        """
        self._db = db

    def get_last_hash(self) -> str:
        """获取最后一条审计日志的 hash。

        供新记录设置 prev_hash 使用。无记录时返回创世 hash。

        Returns:
            str: 最后一条记录的 hash，或 64 个零（创世）
        """
        stmt = select(AuditLog.hash).order_by(AuditLog.id.desc()).limit(1)
        result = self._db.execute(stmt)
        last_hash = result.scalar_one_or_none()
        return last_hash if last_hash else _GENESIS_HASH

    def verify_chain_integrity(
        self,
        *,
        start_id: int = 1,
        limit: Optional[int] = None,
    ) -> ChainIntegrityResult:
        """校验审计日志 hash chain 完整性。

        按 id 顺序遍历，逐条重算 hash 并与存储值比对，同时校验 prev_hash 链式关系。

        Args:
            start_id: 起始校验的记录 ID（默认从头开始）
            limit: 最多校验的记录数（None 表示全部）

        Returns:
            ChainIntegrityResult: 校验结果
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.id >= start_id)
            .order_by(AuditLog.id.asc())
        )
        if limit:
            stmt = stmt.limit(limit)

        records: List[AuditLog] = list(self._db.execute(stmt).scalars().all())

        if not records:
            return ChainIntegrityResult(
                is_valid=True,
                total_checked=0,
                broken_at_id=None,
                broken_reason="",
                last_valid_hash=_GENESIS_HASH,
            )

        expected_prev_hash = _GENESIS_HASH
        # 如果不是从头开始，获取前一条记录的 hash 作为期望的 prev_hash
        if start_id > 1:
            prev_stmt = (
                select(AuditLog.hash)
                .where(AuditLog.id < start_id)
                .order_by(AuditLog.id.desc())
                .limit(1)
            )
            prev_hash = self._db.execute(prev_stmt).scalar_one_or_none()
            if prev_hash:
                expected_prev_hash = prev_hash

        for record in records:
            # 1. 校验 prev_hash 链式关系
            if record.prev_hash != expected_prev_hash:
                return ChainIntegrityResult(
                    is_valid=False,
                    total_checked=records.index(record),
                    broken_at_id=record.id,
                    broken_reason=f"prev_hash 不匹配: 期望={expected_prev_hash[:16]}... 实际={record.prev_hash[:16]}...",
                    last_valid_hash=expected_prev_hash,
                )

            # 2. 重算 hash 并校验
            recomputed_hash = record.compute_hash(record.prev_hash)
            if record.hash != recomputed_hash:
                return ChainIntegrityResult(
                    is_valid=False,
                    total_checked=records.index(record),
                    broken_at_id=record.id,
                    broken_reason=f"hash 不匹配: 存储值={record.hash[:16] if record.hash else 'None'}... 重算值={recomputed_hash[:16]}...",
                    last_valid_hash=expected_prev_hash,
                )

            expected_prev_hash = record.hash

        return ChainIntegrityResult(
            is_valid=True,
            total_checked=len(records),
            broken_at_id=None,
            broken_reason="",
            last_valid_hash=expected_prev_hash,
        )


__all__ = ["AuditChainService", "ChainIntegrityResult"]
