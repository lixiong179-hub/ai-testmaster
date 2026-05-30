"""add ab_test_metrics table

Revision ID: 20260529_add_ab_test_metrics
Revises:
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '20260529_add_ab_test_metrics'
down_revision = '20260529_add_case_refresh_suggestions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ab_test_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('experiment_id', sa.String(length=64), nullable=False),
        sa.Column('variant', sa.String(length=32), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('test_point_id', sa.Integer(), nullable=True),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ab_test_metrics_id'), 'ab_test_metrics', ['id'])
    op.create_index('ix_ab_test_metrics_experiment_id', 'ab_test_metrics', ['experiment_id'])
    op.create_index('ix_ab_test_metrics_project_id', 'ab_test_metrics', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_ab_test_metrics_project_id', table_name='ab_test_metrics')
    op.drop_index('ix_ab_test_metrics_experiment_id', table_name='ab_test_metrics')
    op.drop_index(op.f('ix_ab_test_metrics_id'), table_name='ab_test_metrics')
    op.drop_table('ab_test_metrics')
