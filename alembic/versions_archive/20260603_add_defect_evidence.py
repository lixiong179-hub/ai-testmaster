"""add defect_evidence column to test_results

test_results 表新增 defect_evidence 列（JSON, nullable=True），
用于存储浏览器环境缺陷捕获证据（控制台错误/网络失败/内存泄漏/未捕获异常）。

Revision ID: 20260603_add_defect_evidence
Revises: 20260603_merge_phase4_heads
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

revision = "20260603_add_defect_evidence"
down_revision = "20260603_merge_phase4_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'test_results' "
            "AND COLUMN_NAME = 'defect_evidence'"
        )
    )
    if result.scalar() == 0:
        op.add_column(
            "test_results",
            sa.Column(
                "defect_evidence",
                JSON(),
                nullable=True,
                comment="浏览器缺陷证据（控制台错误/网络失败/内存泄漏/未捕获异常）",
            ),
        )


def downgrade() -> None:
    op.drop_column("test_results", "defect_evidence")
