"""
为测试点独立管理模块补充字段

Revision ID: 20260423_add_test_point_management_fields
Revises: add_test_case_category
Create Date: 2026-04-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260423_add_test_point_management_fields"
down_revision = "add_test_case_category"
branch_labels = None
depends_on = None


def upgrade():
    """新增测试点创建人和测试用例关联测试点字段。"""
    op.add_column(
        "test_points",
        sa.Column("created_by", sa.String(length=100), nullable=True, comment="创建人用户名"),
    )
    op.add_column(
        "test_cases",
        sa.Column("test_point_id", sa.Integer(), nullable=True, comment="关联测试点ID"),
    )
    op.create_index(
        "ix_test_cases_test_point_id",
        "test_cases",
        ["test_point_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_test_cases_test_point_id",
        "test_cases",
        "test_points",
        ["test_point_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    """回滚测试点独立管理模块字段。"""
    op.drop_constraint("fk_test_cases_test_point_id", "test_cases", type_="foreignkey")
    op.drop_index("ix_test_cases_test_point_id", table_name="test_cases")
    op.drop_column("test_cases", "test_point_id")
    op.drop_column("test_points", "created_by")
