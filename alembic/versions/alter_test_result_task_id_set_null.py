"""修改 test_results.task_id 外键：CASCADE -> SET NULL, 允许 NULL

自测数据清理需要删除 TestTask 但保留 TestResult，
因此 task_id 需改为 nullable + ondelete=SET NULL。

Revision ID: alter_test_result_task_id_set_null
Revises: add_review_tables
Create Date: 2026-05-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "alter_test_result_task_id_set_null"
down_revision = "add_review_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "test_results", "task_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.drop_constraint("test_results_ibfk_1", "test_results", type_="foreignkey")
    op.create_foreign_key(
        "test_results_ibfk_1", "test_results", "test_tasks",
        ["task_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("test_results_ibfk_1", "test_results", type_="foreignkey")
    op.create_foreign_key(
        "test_results_ibfk_1", "test_results", "test_tasks",
        ["task_id"], ["id"], ondelete="CASCADE",
    )
    op.alter_column(
        "test_results", "task_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
