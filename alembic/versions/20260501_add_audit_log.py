"""创建 audit_log 表

表结构：
    id, action, actor_id FK(users.id, SET NULL), target_kind, target_id,
    detail JSON, run_id FK(pipeline_runs.id, SET NULL),
    iteration_id FK(iterations.id, SET NULL), created_at

索引：
    ix_audit_log_target (target_kind, target_id)
    ix_audit_log_actor (actor_id)
    ix_audit_log_action (action)
    ix_audit_log_created_at (created_at)

Revision ID: 20260501_add_audit_log
Revises: add_ai_call_log
Create Date: 2026-05-01
"""
import sqlalchemy as sa
from alembic import op


revision = "20260501_add_audit_log"
down_revision = "add_ai_call_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(64), nullable=False, comment="操作类型枚举"),
        sa.Column("actor_id", sa.Integer(), nullable=True, comment="操作人ID"),
        sa.Column("target_kind", sa.String(32), nullable=False, comment="目标实体类型"),
        sa.Column("target_id", sa.Integer(), nullable=False, comment="目标实体ID"),
        sa.Column("detail", sa.JSON(), nullable=True, comment="变更详情"),
        sa.Column("run_id", sa.Integer(), nullable=True, comment="关联PipelineRun"),
        sa.Column("iteration_id", sa.Integer(), nullable=True, comment="关联迭代"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(), comment="操作时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL",
            name="fk_audit_log_actor_id",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["pipeline_runs.id"], ondelete="SET NULL",
            name="fk_audit_log_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["iteration_id"], ["iterations.id"], ondelete="SET NULL",
            name="fk_audit_log_iteration_id",
        ),
    )

    op.create_index(
        "ix_audit_log_target", "audit_log",
        ["target_kind", "target_id"],
    )
    op.create_index(
        "ix_audit_log_actor", "audit_log",
        ["actor_id"],
    )
    op.create_index(
        "ix_audit_log_action", "audit_log",
        ["action"],
    )
    op.create_index(
        "ix_audit_log_created_at", "audit_log",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_table("audit_log")
