"""add case_category to test_cases

Revision ID: a1b2c3d4e5f6
Revises: 54cbd326407e
Create Date: 2026-06-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "54cbd326407e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column(
            "case_category",
            sa.String(20),
            nullable=True,
            comment="用例场景分类：positive/boundary/exception/security/performance",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_cases", "case_category")
