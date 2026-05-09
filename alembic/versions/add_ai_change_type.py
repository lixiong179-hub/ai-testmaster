"""add ai_change_type column to test_cases

Revision ID: add_ai_change_type
Revises: add_pipeline_metrics
Create Date: 2026-05-06 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_ai_change_type'
down_revision = 'add_pipeline_metrics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'test_cases',
        sa.Column('ai_change_type', sa.String(20), nullable=True,
                  comment='AI评审结果：added=查漏新增/modified=补缺修正/deprecated=去冗废弃'),
    )


def downgrade() -> None:
    op.drop_column('test_cases', 'ai_change_type')
