"""add snapshot_version_id to case_refresh_suggestions

Revision ID: 20260530_add_snapshot_version_id
Revises: 20260529_add_ab_test_metrics
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = '20260530_add_snapshot_version_id'
down_revision = '20260529_add_ab_test_metrics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'case_refresh_suggestions',
        sa.Column('snapshot_version_id', sa.Integer(), nullable=True, comment='应用时创建的快照版本ID(TestCaseVersion.id)，用于回滚'),
    )
    op.create_index('ix_case_refresh_suggestions_snapshot_version_id', 'case_refresh_suggestions', ['snapshot_version_id'])
    op.create_foreign_key(
        'fk_case_refresh_suggestions_snapshot_version_id',
        'case_refresh_suggestions',
        'test_case_versions',
        ['snapshot_version_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_case_refresh_suggestions_snapshot_version_id', 'case_refresh_suggestions', type_='foreignkey')
    op.drop_index('ix_case_refresh_suggestions_snapshot_version_id', table_name='case_refresh_suggestions')
    op.drop_column('case_refresh_suggestions', 'snapshot_version_id')
