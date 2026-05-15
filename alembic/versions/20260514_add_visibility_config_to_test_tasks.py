import sqlalchemy as sa
from alembic import op


revision = "20260514_add_visibility_config_to_test_tasks"
down_revision = "20260514_add_enable_posterior_scoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_tasks",
        sa.Column(
            "visibility_config",
            sa.JSON(),
            nullable=True,
            comment="可见模式配置",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_tasks", "visibility_config")
