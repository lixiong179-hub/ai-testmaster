"""add quality_rule_configs table

Revision ID: 20260602_add_quality_rule_configs
Revises: 20260602_add_feature_flags
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = '20260602_add_quality_rule_configs'
down_revision = '20260602_add_feature_flags'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'quality_rule_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('rule_key', sa.String(length=80), nullable=False),
        sa.Column('rule_value', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_quality_rule_project_key',
        'quality_rule_configs',
        ['project_id', 'rule_key'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_quality_rule_project_key', table_name='quality_rule_configs')
    op.drop_table('quality_rule_configs')
