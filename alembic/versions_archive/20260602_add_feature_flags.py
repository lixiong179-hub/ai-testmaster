"""add feature_flags table

Revision ID: 20260602_add_feature_flags
Revises: 5ff2f5eaa8da
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = '20260602_add_feature_flags'
down_revision = '5ff2f5eaa8da'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'feature_flags',
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('rollout_percentage', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('target_project_ids', sa.JSON(), nullable=True),
        sa.Column('target_type', sa.String(length=20), nullable=False, server_default='all'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('feature_flags')
