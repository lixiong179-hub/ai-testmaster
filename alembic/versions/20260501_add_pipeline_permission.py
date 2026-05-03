"""创建 pipeline_roles, pipeline_permissions, pipeline_user_role 表

表结构：
    pipeline_roles: id, name VARCHAR(32) UNIQUE, description, created_at
    pipeline_permissions: id, role_id FK, resource VARCHAR(32), action VARCHAR(32), scope VARCHAR(16)
    pipeline_user_role: id, user_id FK, role_id FK, project_id FK, created_at

Revision ID: 20260501_add_pipeline_permission
Revises: 20260501_add_pipeline_config
Create Date: 2026-05-01
"""
import sqlalchemy as sa
from alembic import op


revision = "20260501_add_pipeline_permission"
down_revision = "20260501_add_pipeline_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(32), nullable=False, comment="角色名"),
        sa.Column("description", sa.String(256), nullable=True, comment="角色描述"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_pipeline_role_name"),
    )

    op.create_table(
        "pipeline_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("resource", sa.String(32), nullable=False, comment="资源类型"),
        sa.Column("action", sa.String(32), nullable=False, comment="操作类型"),
        sa.Column("scope", sa.String(16), nullable=False, server_default="project", comment="范围"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["role_id"], ["pipeline_roles.id"], ondelete="CASCADE",
            name="fk_pipeline_permission_role_id",
        ),
        sa.UniqueConstraint(
            "role_id", "resource", "action", "scope",
            name="uq_pipeline_permission",
        ),
    )
    op.create_index(
        "ix_pipeline_permission_role", "pipeline_permissions", ["role_id"],
    )

    op.create_table(
        "pipeline_user_role",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_pipeline_user_role_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["pipeline_roles.id"], ondelete="CASCADE",
            name="fk_pipeline_user_role_role_id",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE",
            name="fk_pipeline_user_role_project_id",
        ),
        sa.UniqueConstraint(
            "user_id", "role_id", "project_id",
            name="uq_pipeline_user_role",
        ),
    )
    op.create_index(
        "ix_pipeline_user_role_user", "pipeline_user_role", ["user_id"],
    )
    op.create_index(
        "ix_pipeline_user_role_project", "pipeline_user_role", ["project_id"],
    )


def downgrade() -> None:
    op.drop_table("pipeline_user_role")
    op.drop_index("ix_pipeline_permission_role", table_name="pipeline_permissions")
    op.drop_table("pipeline_permissions")
    op.drop_table("pipeline_roles")
