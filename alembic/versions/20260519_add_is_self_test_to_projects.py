import sqlalchemy as sa
from alembic import op


revision = "20260519_add_is_self_test_to_projects"
down_revision = "20260514_add_visibility_config_to_test_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "is_self_test",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="是否自测项目",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "is_self_test")
