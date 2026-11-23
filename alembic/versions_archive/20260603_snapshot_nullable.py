"""snapshot_data nullable for archive strategy

Revision ID: 20260603_snapshot_nullable
Revises: 20260602_add_quality_rule_configs
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260603_snapshot_nullable"
down_revision = "20260602_add_quality_rule_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "test_case_versions",
        "snapshot_data",
        existing_type=sa.JSON(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "test_case_versions",
        "snapshot_data",
        existing_type=sa.JSON(),
        nullable=False,
    )
