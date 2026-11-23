"""修改element_locators.step_id为nullable，支持前置条件步骤

前置条件步骤的ElementLocator记录不关联test_steps表，
step_id需要允许为NULL，仅通过precondition_step_id关联。

Revision ID: make_step_id_nullable
Revises: add_precondition_steps_table
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'make_step_id_nullable'
down_revision = 'add_precondition_steps_table'
branch_labels = None
depends_on = None


def upgrade():
    """修改 step_id 列为 nullable"""
    op.alter_column(
        'element_locators',
        'step_id',
        existing_type=sa.Integer(),
        nullable=True,
        comment='关联的测试步骤ID（前置条件步骤时为NULL）'
    )


def downgrade():
    """回滚：将 step_id 改回 NOT NULL"""
    # 注意：回滚前需确保没有 step_id 为 NULL 的记录
    op.alter_column(
        'element_locators',
        'step_id',
        existing_type=sa.Integer(),
        nullable=False,
        comment='关联的测试步骤ID'
    )
