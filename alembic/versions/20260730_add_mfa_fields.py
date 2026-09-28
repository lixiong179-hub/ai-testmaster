"""add mfa fields to users table

Revision ID: 20260730_add_mfa_fields
Revises: 20260729_add_visual_ai_tables
Create Date: 2026-07-30

Phase 3 Task 3: MFA 多因子认证 — 用户表新增 mfa_secret/mfa_enabled/mfa_backup_codes 字段。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260730_add_mfa_fields"
down_revision = "20260729_add_visual_ai_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 MFA 字段到 users 表。"""
    op.add_column("users", sa.Column("mfa_secret", sa.String(64), nullable=True, comment="MFA TOTP 密钥（Base32）"))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="MFA 是否已启用"))
    op.add_column("users", sa.Column("mfa_backup_codes", sa.JSON(), nullable=True, comment="MFA 备份码（bcrypt 哈希）"))


def downgrade() -> None:
    """回滚 MFA 字段。"""
    op.drop_column("users", "mfa_backup_codes")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
