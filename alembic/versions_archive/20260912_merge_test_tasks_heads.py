"""merge add_err_msg_test_tasks and 20260912_add_priority_to_test_tasks heads

两个 head 均为 test_tasks 表新增列：
- add_err_msg_test_tasks: 新增 error_message 列（超时任务自动停止，P1 E-08）
- 20260912_add_priority_to_test_tasks: 新增 priority 列（执行队列排序，Task E-06）
二者互相独立、无冲突，故合并为单一 head。

Revision ID: 20260912_merge_test_tasks_heads
Revises: 20260912_add_priority_to_test_tasks, add_err_msg_test_tasks
Create Date: 2026-09-12
"""
from alembic import op

revision = "20260912_merge_test_tasks_heads"
down_revision = ("20260912_add_priority_to_test_tasks", "add_err_msg_test_tasks")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
