"""add_test_type_to_test_points

Revision ID: 54cbd326407e
Revises: 20260605_content_mediumtext
Create Date: 2026-06-09 10:34:12.244066

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "54cbd326407e"
down_revision: Union[str, None] = "20260605_content_mediumtext"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_points",
        sa.Column(
            "test_type",
            sa.String(20),
            nullable=False,
            server_default="functional",
            comment="测试类型：functional/boundary/exception/ui/security/performance",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_points", "test_type")
