"""创建 pipeline_config 表

表结构：
    id, key VARCHAR(128) UNIQUE, value TEXT, value_type VARCHAR(8),
    description TEXT, updated_by INT, updated_at DATETIME

Revision ID: 20260501_add_pipeline_config
Revises: 20260501_add_audit_log
Create Date: 2026-05-01
"""
import sqlalchemy as sa
from alembic import op


revision = "20260501_add_pipeline_config"
down_revision = "20260501_add_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(128), nullable=False, comment="配置项键名"),
        sa.Column("value", sa.Text(), nullable=False, comment="配置项值"),
        sa.Column("value_type", sa.String(8), nullable=False, server_default="str", comment="值类型"),
        sa.Column("description", sa.Text(), nullable=True, comment="配置项说明"),
        sa.Column("updated_by", sa.Integer(), nullable=True, comment="最后修改人ID"),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(), comment="最后修改时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_pipeline_config_key"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_config")
