"""
合并测试点管理与前置条件迁移分支

Revision ID: 20260423_merge_heads
Revises: 20260423_add_test_point_management_fields, make_step_id_nullable
Create Date: 2026-04-23 18:10:00.000000
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260423_merge_heads"
down_revision = ("20260423_add_test_point_management_fields", "make_step_id_nullable")
branch_labels = None
depends_on = None


def upgrade():
    """合并双 head，不执行额外结构变更。"""


def downgrade():
    """回退为双 head 状态，不执行额外结构变更。"""
