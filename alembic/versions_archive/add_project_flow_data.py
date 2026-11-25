"""add project_flow_data table

Revision ID: add_project_flow_data
Revises: add_ai_change_type
Create Date: 2026-05-07 13:15:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_project_flow_data'
down_revision = 'add_ai_change_type'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'project_flow_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'project_id',
            sa.Integer(),
            sa.ForeignKey('projects.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('flow_data', sa.JSON(), nullable=False),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.Column('update_time', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id'),
    )
    op.create_index(
        op.f('ix_project_flow_data_id'), 'project_flow_data', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_project_flow_data_project_id'),
        'project_flow_data',
        ['project_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_project_flow_data_project_id'), table_name='project_flow_data'
    )
    op.drop_index(op.f('ix_project_flow_data_id'), table_name='project_flow_data')
    op.drop_table('project_flow_data')
