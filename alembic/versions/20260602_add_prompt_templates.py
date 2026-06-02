"""add prompt_templates table

Revision ID: 20260602_add_prompt_templates
Revises: 20260602_add_feature_flags
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260602_add_prompt_templates"
down_revision = "20260602_add_feature_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prompt_key", sa.String(length=80), nullable=False, comment="Prompt唯一标识键"),
        sa.Column("prompt_version", sa.Integer(), nullable=False, comment="版本号，同一key内自增"),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False, comment="内容SHA256哈希"),
        sa.Column(
            "content",
            sa.Text().with_variant(sa.dialects.mysql.MEDIUMTEXT(), "mysql"),
            nullable=False,
            comment="Prompt内容",
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("0"),
            comment="是否为当前key的默认版本",
        ),
        sa.Column("description", sa.String(length=500), nullable=True, comment="版本描述"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_key", "prompt_version", name="uq_prompt_key_version"),
    )
    op.create_index("ix_prompt_templates_prompt_key", "prompt_templates", ["prompt_key"])


def downgrade() -> None:
    op.drop_index("ix_prompt_templates_prompt_key", table_name="prompt_templates")
    op.drop_table("prompt_templates")
