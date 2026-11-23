import sqlalchemy as sa
from alembic import op


revision = "20260519_add_source_to_bugs"
down_revision = "20260519_add_is_self_test_to_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bugs",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="manual",
            comment="Bug来源: manual/self_test",
        ),
    )


def downgrade() -> None:
    op.drop_column("bugs", "source")
