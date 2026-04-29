"""add test_cases lifecycle_status + summary + lineage fields + indexes

Revision ID: 20260429_add_tc_lifecycle_lineage
Revises: 20260429_add_tp_version_status
Create Date: 2026-04-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20260429_add_tc_lifecycle_lineage"
down_revision = "20260429_add_tp_version_status"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 添加 lifecycle_status 列（默认值 active）
    op.add_column(
        "test_cases",
        sa.Column("lifecycle_status", sa.String(30), nullable=False, server_default="active",
                  comment="生命周期状态：draft/active/pending_review/needs_modify/locator_broken/deprecated/archived"),
    )

    # 2. 添加 summary 列
    op.add_column(
        "test_cases",
        sa.Column("summary", sa.Text(), nullable=True, comment="AI生成的用例摘要"),
    )

    # 3. 添加 summary_version 列（默认值 0）
    op.add_column(
        "test_cases",
        sa.Column("summary_version", sa.Integer(), nullable=False, server_default="0",
                  comment="摘要版本号，0=未生成"),
    )

    # 4. 添加 summary_model_version 列
    op.add_column(
        "test_cases",
        sa.Column("summary_model_version", sa.String(64), nullable=True,
                  comment="生成摘要的AI模型版本"),
    )

    # 5. 添加 parent_case_id 列 + 外键（MySQL会自动为FK创建索引，无需单独建索引）
    op.add_column(
        "test_cases",
        sa.Column("parent_case_id", sa.Integer(), nullable=True, comment="父用例ID，用于用例衍生/拆分"),
    )
    op.create_foreign_key(
        "fk_test_cases_parent_case_id",
        "test_cases", "test_cases",
        ["parent_case_id"], ["id"],
        ondelete="SET NULL",
    )

    # 6. 添加 last_review_id 列 + 外键
    op.add_column(
        "test_cases",
        sa.Column("last_review_id", sa.Integer(), nullable=True, comment="最近一次评审ID"),
    )
    op.create_foreign_key(
        "fk_test_cases_last_review_id",
        "test_cases", "code_reviews",
        ["last_review_id"], ["id"],
        ondelete="SET NULL",
    )

    # 7. 添加复合索引 (project_id, lifecycle_status)
    op.create_index(
        "ix_test_cases_project_lifecycle",
        "test_cases",
        ["project_id", "lifecycle_status"],
    )


def downgrade():
    # 动态查找实际FK约束名（MySQL可能自动命名，与指定名不同）
    conn = op.get_bind()
    insp = inspect(conn)
    fk_names = {fk["constrained_columns"][0]: fk["name"] for fk in insp.get_foreign_keys("test_cases")}

    # 1. 删除外键约束（必须先于列删除）
    if "last_review_id" in fk_names:
        op.drop_constraint(fk_names["last_review_id"], "test_cases", type_="foreignkey")
    if "parent_case_id" in fk_names:
        op.drop_constraint(fk_names["parent_case_id"], "test_cases", type_="foreignkey")

    # 2. 删除索引
    index_names = {idx["name"] for idx in insp.get_indexes("test_cases")}
    if "ix_test_cases_project_lifecycle" in index_names:
        op.drop_index("ix_test_cases_project_lifecycle", table_name="test_cases")

    # 3. 删除列
    col_names = {c["name"] for c in insp.get_columns("test_cases")}
    for col in ["last_review_id", "parent_case_id", "summary_model_version",
                "summary_version", "summary", "lifecycle_status"]:
        if col in col_names:
            op.drop_column("test_cases", col)
