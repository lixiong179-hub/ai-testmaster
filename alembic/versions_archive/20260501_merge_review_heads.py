"""merge review heads

Revision ID: merge_review_heads
Revises: 20260429_add_tc_lifecycle_lineage, 20260501_add_pipeline_permission, add_review_tables
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_review_heads'
down_revision = ('20260429_add_tc_lifecycle_lineage', '20260501_add_pipeline_permission', 'add_review_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
