"""
新增 test_points 表的 test_type/expected_result/precondition 列

测试点 Schema 增强：新增测试类型、预期结果、前置条件字段，
提升 AI 生成测试点的结构化程度和可执行性。

Revision ID: 20260604_add_test_point_fields
Revises: 20260603_merge_phase4_heads
Create Date: 2026-06-04 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20260604_add_test_point_fields"
down_revision = "20260603_merge_phase4_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("test_points", sa.Column("test_type", sa.String(20), nullable=False, server_default="functional", comment="测试类型：functional/boundary/exception/ui/security/performance"))
    op.add_column("test_points", sa.Column("expected_result", sa.String(500), nullable=False, server_default="", comment="预期结果描述"))
    op.add_column("test_points", sa.Column("precondition", sa.String(500), nullable=False, server_default="", comment="前置条件"))


def downgrade():
    op.drop_column("test_points", "precondition")
    op.drop_column("test_points", "expected_result")
    op.drop_column("test_points", "test_type")
