"""
删除 test_points 表的 function 列

function 字段已弃用，与 module/point 信息冗余且 AI 解析不准确。

Revision ID: 20260427_drop_function
Revises: 20260423_merge_heads
Create Date: 2026-04-27 19:30:00.000000
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260427_drop_function"
down_revision = "20260423_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("test_points", "function")


def downgrade():
    op.add_column("test_points", sa.Column("function", sa.String(200), nullable=False, server_default="", comment="功能名称"))
