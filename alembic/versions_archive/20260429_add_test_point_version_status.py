"""add test_points.version + test_points.status + index

Revision ID: 20260429_add_tp_version_status
Revises: 20260429_add_capability
Create Date: 2026-04-29
"""
import sqlalchemy as sa
from alembic import op


revision = "20260429_add_tp_version_status"
down_revision = "20260429_add_capability"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 添加 version 列（默认值 1）
    op.add_column(
        "test_points",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1", comment="版本号，每次变更递增"),
    )

    # 2. 添加 status 列（默认值 active）
    op.add_column(
        "test_points",
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="状态：draft/active/deprecated/archived"),
    )

    # 3. 添加复合索引 (capability_id, status)
    op.create_index(
        "ix_test_points_capability_status",
        "test_points",
        ["capability_id", "status"],
    )


def downgrade():
    # 1. 删除复合索引
    op.drop_index("ix_test_points_capability_status", table_name="test_points")

    # 2. 删除 status 列
    op.drop_column("test_points", "status")

    # 3. 删除 version 列
    op.drop_column("test_points", "version")
