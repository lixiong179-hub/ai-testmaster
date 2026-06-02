"""add case_number_seqs table and TestCase.legacy_case_no

Revision ID: 20260602_add_case_number_seq
Revises: 5ff2f5eaa8da
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa

revision = "20260602_add_case_number_seq"
down_revision = "5ff2f5eaa8da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_number_seqs",
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID，同时为主键"),
        sa.Column("current_seq", sa.Integer(), nullable=False, server_default="0", comment="当前已分配的最大序号"),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "legacy_case_no",
            sa.String(80),
            nullable=True,
            comment="历史用例编号，Excel导入时保留原始编号",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_cases", "legacy_case_no")
    op.drop_table("case_number_seqs")
