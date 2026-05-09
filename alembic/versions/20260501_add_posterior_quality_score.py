"""add posterior_quality_score to test_cases

Revision ID: 20260501_add_posterior_quality_score
Revises:
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260501_add_posterior_quality_score"
down_revision = "merge_review_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column(
            "posterior_quality_score",
            sa.Float(),
            nullable=True,
            comment="后验质量分（0-100），评审+执行后回填",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_cases", "posterior_quality_score")
