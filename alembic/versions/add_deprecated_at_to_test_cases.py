"""
添加 deprecated_at 字段到 test_cases 表

用于精确记录用例进入 deprecated 状态的时间戳，
替代之前使用 update_time 近似计算冷却期的方案。

Revision ID: add_deprecated_at
Revises: add_test_case_category
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_deprecated_at'
down_revision = 'add_test_case_category'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('test_cases', sa.Column(
        'deprecated_at', sa.DateTime(), nullable=True,
        comment='进入deprecated状态的时间戳，用于冷却期计算',
    ))


def downgrade():
    op.drop_column('test_cases', 'deprecated_at')
