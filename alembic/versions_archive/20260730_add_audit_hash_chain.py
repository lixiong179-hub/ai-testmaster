"""add hash chain fields to audit_log

Revision ID: 20260730_add_audit_hash_chain
Revises: 20260730_add_mfa_fields
Create Date: 2026-07-30

Phase 3 Task 10: 审计日志 hash chain — audit_log 表新增 prev_hash/hash 字段。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260730_add_audit_hash_chain"
down_revision = "20260730_add_mfa_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 hash chain 字段到 audit_log 表。"""
    # prev_hash: 上一条记录的 hash，首条为 64 个零
    op.add_column("audit_log", sa.Column("prev_hash", sa.String(64), nullable=False, server_default="0" * 64, comment="上一条记录的 hash"))
    # hash: 本条记录的 hash（before_flush 时计算）
    op.add_column("audit_log", sa.Column("hash", sa.String(64), nullable=True, comment="本条记录的 hash"))


def downgrade() -> None:
    """回滚 hash chain 字段。"""
    op.drop_column("audit_log", "hash")
    op.drop_column("audit_log", "prev_hash")
