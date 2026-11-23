import sqlalchemy as sa
from alembic import op


revision = "20260519_add_self_test_schedule_to_projects"
down_revision = "20260519_add_source_to_bugs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "self_test_schedule",
            sa.String(100),
            nullable=True,
            comment="自测定时执行cron表达式",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "self_test_schedule")
