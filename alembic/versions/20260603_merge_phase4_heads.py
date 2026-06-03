"""merge phase4 migration heads

Revision ID: 20260603_merge_phase4_heads
Revises: 20260603_snapshot_nullable, 20260602_add_ai_call_log_audit, 20260602_add_case_number_seq
Create Date: 2026-06-03
"""
from alembic import op

revision = "20260603_merge_phase4_heads"
down_revision = ("20260603_snapshot_nullable", "20260602_add_ai_call_log_audit", "20260602_add_case_number_seq")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
