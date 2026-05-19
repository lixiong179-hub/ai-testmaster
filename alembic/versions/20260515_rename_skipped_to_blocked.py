"""
重命名 test_reports.skipped_cases 为 blocked_cases

exec_status=3 的语义从"跳过"统一为"阻塞"，
数据库列名同步更新。

Revision ID: rename_skipped_to_blocked
Revises: add_enable_posterior_scoring
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'rename_skipped_to_blocked'
down_revision = 'add_enable_posterior_scoring'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'test_reports', 'skipped_cases',
        new_column_name='blocked_cases',
        existing_type=sa.Integer(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        'test_reports', 'blocked_cases',
        new_column_name='skipped_cases',
        existing_type=sa.Integer(),
        existing_nullable=True,
    )
