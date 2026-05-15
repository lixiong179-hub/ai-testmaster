import sqlalchemy as sa
from alembic import op


revision = "20260514_add_enable_posterior_scoring"
down_revision = "add_project_flow_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_config",
        sa.Column(
            "enable_posterior_scoring",
            sa.Boolean(),
            nullable=False,
            server_default="0",
            comment="Pipeline完成后是否触发后验评分",
        ),
    )


def downgrade() -> None:
    op.drop_column("pipeline_config", "enable_posterior_scoring")
