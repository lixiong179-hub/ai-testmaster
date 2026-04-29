"""add test_capabilities table + test_points.capability_id FK

Revision ID: 20260429_add_capability
Revises: 20260429_merge_heads
Create Date: 2026-04-29
"""
import sqlalchemy as sa
from alembic import op


revision = "20260429_add_capability"
down_revision = "20260429_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建 test_capabilities 表
    op.create_table(
        "test_capabilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="关联项目ID"),
        sa.Column("key", sa.String(100), nullable=False, comment="能力唯一标识"),
        sa.Column("title", sa.String(255), nullable=False, comment="能力显示名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="能力描述"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="能力状态"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "key", name="uq_test_capability_project_key"),
    )
    op.create_index("ix_test_capability_project_status", "test_capabilities", ["project_id", "status"])

    # 2. 给 test_points 添加 capability_id 外键
    op.add_column(
        "test_points",
        sa.Column("capability_id", sa.Integer(), nullable=True, comment="关联业务能力ID"),
    )
    op.create_index("ix_test_points_capability_id", "test_points", ["capability_id"])
    op.create_foreign_key(
        "fk_test_points_capability_id",
        "test_points",
        "test_capabilities",
        ["capability_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # 1. 删除 test_points 的 capability_id 外键
    op.drop_constraint("fk_test_points_capability_id", "test_points", type_="foreignkey")
    op.drop_index("ix_test_points_capability_id", table_name="test_points")
    op.drop_column("test_points", "capability_id")

    # 2. 删除 test_capabilities 表
    op.drop_index("ix_test_capability_project_status", table_name="test_capabilities")
    op.drop_table("test_capabilities")
