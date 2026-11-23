"""add execution_failure_type and last_verified_at to test_cases

Revision ID: c9d0e1f2a3b4
Revises: 20260616_add_uq_review_lock_target
Create Date: 2026-06-24

新增2个执行验证字段：
    - execution_failure_type: 执行失败类型分类（仅在验证失败时记录）
    - last_verified_at: 最近一次执行验证时间戳
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "20260616_add_uq_review_lock_target"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增执行失败类型和最近验证时间字段。"""
    op.add_column(
        "test_cases",
        sa.Column(
            "execution_failure_type",
            sa.String(50),
            nullable=True,
            comment="执行失败类型：element_not_found/timeout/assertion_failed/network_error/other，null表示未验证或验证通过",
        ),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "last_verified_at",
            sa.DateTime,
            nullable=True,
            comment="最近一次执行验证时间戳",
        ),
    )


def downgrade() -> None:
    """删除执行失败类型和最近验证时间字段。"""
    op.drop_column("test_cases", "last_verified_at")
    op.drop_column("test_cases", "execution_failure_type")
