"""merge test_point_fields and ux_category heads

Revision ID: 20260604_merge_heads
Revises: 20260604_add_test_point_fields, 20260603_add_ux_category_to_bugs
Create Date: 2026-06-04
"""
from alembic import op

revision = "20260604_merge_heads"
down_revision = ("20260604_add_test_point_fields", "20260603_add_ux_category_to_bugs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
