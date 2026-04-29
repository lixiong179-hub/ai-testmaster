"""merge heads: 20260424_remove_iteration_id_sentinel + 20260429_add_capability

Revision ID: 20260429_merge_heads
Revises: 20260424_remove_iteration_id_sentinel, 20260427_drop_function
Create Date: 2026-04-29
"""
from alembic import op


revision = "20260429_merge_heads"
down_revision = ("20260424_remove_iteration_id_sentinel", "20260427_drop_function")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
