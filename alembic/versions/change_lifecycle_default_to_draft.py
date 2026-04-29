"""
修改 test_cases.lifecycle_status 默认值从 'active' 改为 'draft'

按状态机设计，AI 生成的新用例应从 draft 开始，
而非直接进入 active 状态。

Revision ID: change_lc_default_draft
Revises: add_deprecated_at
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'change_lc_default_draft'
down_revision = 'add_deprecated_at'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'test_cases', 'lifecycle_status',
        existing_type=sa.String(30),
        nullable=False,
        server_default='draft',
        existing_server_default='active',
    )


def downgrade():
    op.alter_column(
        'test_cases', 'lifecycle_status',
        existing_type=sa.String(30),
        nullable=False,
        server_default='active',
        existing_server_default='draft',
    )
