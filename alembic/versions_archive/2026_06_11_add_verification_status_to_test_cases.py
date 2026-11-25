"""add verification status fields to test_cases

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增4个验证状态字段：元素验证率、执行验证、自愈修复标记、锚定来源。"""
    op.add_column(
        "test_cases",
        sa.Column(
            "element_verified_ratio",
            sa.Float,
            nullable=True,
            comment="元素验证率（0.0-1.0），null表示未验证",
        ),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "execution_verified",
            sa.Boolean,
            nullable=True,
            comment="执行验证是否通过，null表示未验证",
        ),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "self_healed",
            sa.Boolean,
            nullable=True,
            comment="是否经过自愈修复，null表示未修复",
        ),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "grounding_source",
            sa.String(20),
            nullable=True,
            comment="锚定来源：dom_api/text_only",
        ),
    )


def downgrade() -> None:
    """删除4个验证状态字段。"""
    op.drop_column("test_cases", "grounding_source")
    op.drop_column("test_cases", "self_healed")
    op.drop_column("test_cases", "execution_verified")
    op.drop_column("test_cases", "element_verified_ratio")
