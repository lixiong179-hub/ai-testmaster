"""add priority column to test_tasks table

Revision ID: 20260912_add_priority_to_test_tasks
Revises: 20260730_add_saml_fields
Create Date: 2026-09-12

Task E-06: 执行队列排序功能 — 为 test_tasks 表新增 priority 字段，作为执行
队列排序的核心维度（1高/2中/3低）。配套后端 sort_by=priority 排序能力，使
任务列表可按优先级排序展示，便于高优先级任务优先调度与查看。

迁移内容：
    1. test_tasks 表新增 priority（INT NOT NULL DEFAULT 2）
       - 默认值 2（中优先级），保证历史任务回填后语义一致
       - 加索引加速按优先级排序/筛选
    2. 回滚：删除 priority 列及其索引

设计说明：
    - server_default='2' 用于回填历史行，迁移完成后历史任务均为中优先级
    - 模型层 default=2 保证 ORM 创建任务时未指定 priority 的默认值
    - 1=高 / 2=中 / 3=低，与 test_cases / test_points 的 priority 语义对齐
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260912_add_priority_to_test_tasks"
down_revision = "20260730_add_saml_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为 test_tasks 表新增 priority 字段并建立索引。"""
    op.add_column(
        "test_tasks",
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="2",
            comment="优先级：1高/2中/3低",
        ),
    )
    op.create_index("ix_test_tasks_priority", "test_tasks", ["priority"])


def downgrade() -> None:
    """回滚 priority 字段。"""
    op.drop_index("ix_test_tasks_priority", table_name="test_tasks")
    op.drop_column("test_tasks", "priority")
