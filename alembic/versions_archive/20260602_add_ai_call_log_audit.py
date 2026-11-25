"""add audit enhancement fields to ai_call_log

Revision ID: 20260602_add_ai_call_log_audit
Revises: 20260602_add_prompt_templates
Create Date: 2026-06-02

新增字段：
    generation_batch_id  FK(generation_batches.id, SET NULL)
    scenario_type        String(50)
    generation_strategy  String(50)
    prompt_key           String(80)
    prompt_version       Integer
    prompt_hash          String(64)
    error_code           String(30)
"""
from alembic import op
import sqlalchemy as sa

revision = "20260602_add_ai_call_log_audit"
down_revision = "20260602_add_prompt_templates"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_call_log",
        sa.Column("generation_batch_id", sa.Integer(), nullable=True, comment="关联生成批次ID"),
    )
    op.add_column(
        "ai_call_log",
        sa.Column("scenario_type", sa.String(50), nullable=True, comment="资料组合场景"),
    )
    op.add_column(
        "ai_call_log",
        sa.Column("generation_strategy", sa.String(50), nullable=True, comment="生成策略"),
    )
    op.add_column(
        "ai_call_log",
        sa.Column("prompt_key", sa.String(80), nullable=True, comment="Prompt模板键"),
    )
    op.add_column(
        "ai_call_log",
        sa.Column("prompt_version", sa.Integer(), nullable=True, comment="Prompt版本号"),
    )
    op.add_column(
        "ai_call_log",
        sa.Column("prompt_hash", sa.String(64), nullable=True, comment="Prompt内容哈希"),
    )
    op.add_column(
        "ai_call_log",
        sa.Column("error_code", sa.String(30), nullable=True, comment="错误码枚举值"),
    )
    op.create_index(
        "ix_ai_call_log_generation_batch_id",
        "ai_call_log",
        ["generation_batch_id"],
    )
    op.create_foreign_key(
        "fk_ai_call_log_generation_batch_id",
        "ai_call_log",
        "generation_batches",
        ["generation_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_ai_call_log_generation_batch_id", "ai_call_log", type_="foreignkey")
    op.drop_index("ix_ai_call_log_generation_batch_id", table_name="ai_call_log")
    op.drop_column("ai_call_log", "error_code")
    op.drop_column("ai_call_log", "prompt_hash")
    op.drop_column("ai_call_log", "prompt_version")
    op.drop_column("ai_call_log", "prompt_key")
    op.drop_column("ai_call_log", "generation_strategy")
    op.drop_column("ai_call_log", "scenario_type")
    op.drop_column("ai_call_log", "generation_batch_id")
