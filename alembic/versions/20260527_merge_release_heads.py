"""Merge release migration heads.

Revision ID: 20260527_merge_release_heads
Revises: 20260519_add_self_test_schedule_to_projects, 20260522_add_migration_fields, add_dependency_chain_fields, alter_test_result_task_id_set_null
Create Date: 2026-05-27
"""

revision = "20260527_merge_release_heads"
down_revision = (
    "20260519_add_self_test_schedule_to_projects",
    "20260522_add_migration_fields",
    "add_dependency_chain_fields",
    "alter_test_result_task_id_set_null",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
