"""add ux_category column to bugs

bugs 表新增 ux_category 列（String(50), nullable=True），
用于 UX 缺陷分类（loading_experience/error_feedback/response_performance/
visual_consistency/empty_state/security），应用层校验，不使用 SQL Enum。

Revision ID: 20260603_add_ux_category_to_bugs
Revises: 20260603_add_defect_evidence
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260603_add_ux_category_to_bugs"
down_revision = "20260603_add_defect_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME = 'bugs' "
            "AND COLUMN_NAME = 'ux_category'"
        )
    )
    if result.scalar() == 0:
        op.add_column(
            "bugs",
            sa.Column(
                "ux_category",
                sa.String(50),
                nullable=True,
                comment="UX缺陷分类: loading_experience/error_feedback/response_performance/visual_consistency/empty_state/security",
            ),
        )


def downgrade() -> None:
    op.drop_column("bugs", "ux_category")
