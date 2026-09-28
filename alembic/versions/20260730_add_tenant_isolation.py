"""add tenant isolation: tenants table + tenant_id on core business tables

Revision ID: 20260730_add_tenant_isolation
Revises: 20260730_add_audit_hash_chain
Create Date: 2026-07-30

Phase 3 Task 9: 租户行级安全 — 创建 tenants 表 + 11 张核心业务表添加 tenant_id 列。

迁移内容：
    1. 创建 tenants 表（租户主表）
    2. 为 11 张核心业务表添加 tenant_id 列 + 索引 + 外键：
       users, projects, project_files, test_cases, test_tasks, test_results,
       test_reports, iterations, test_points, test_capabilities, requirements

设计说明：
    - tenant_id 可为 NULL（兼容存量数据 + 系统级用户如 superadmin）
    - 外键 ON DELETE CASCADE（租户删除时级联清除业务数据，users 为 SET NULL）
    - 索引加速按租户过滤查询
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260730_add_tenant_isolation"
down_revision = "20260730_add_audit_hash_chain"
branch_labels = None
depends_on = None


# 需要添加 tenant_id 的核心业务表清单
# (表名, 外键删除策略) — users 为 SET NULL（保留用户），其余为 CASCADE
_TENANT_AWARE_TABLES = [
    ("users", "SET NULL"),
    ("projects", "CASCADE"),
    ("project_files", "CASCADE"),
    ("test_cases", "CASCADE"),
    ("test_tasks", "CASCADE"),
    ("test_results", "CASCADE"),
    ("test_reports", "CASCADE"),
    ("iterations", "CASCADE"),
    ("test_points", "CASCADE"),
    ("test_capabilities", "CASCADE"),
    ("requirements", "CASCADE"),
]


def upgrade() -> None:
    """创建 tenants 表 + 为核心业务表添加 tenant_id 列。"""
    # 1. 创建 tenants 表
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, comment="租户名称（企业/组织名）"),
        sa.Column("slug", sa.String(50), nullable=False, unique=True, comment="URL 友好唯一标识"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", comment="状态: active/suspended/deleted"),
        sa.Column("max_projects", sa.Integer, nullable=False, server_default="100", comment="最大项目数配额"),
        sa.Column("max_users", sa.Integer, nullable=False, server_default="50", comment="最大用户数配额"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("1"), comment="是否激活"),
        sa.Column("create_time", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("update_time", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        comment="租户表 — 多租户隔离基础",
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # 2. 为核心业务表添加 tenant_id 列 + 索引 + 外键
    for table_name, ondelete in _TENANT_AWARE_TABLES:
        # 添加列（nullable=True 兼容存量数据）
        op.add_column(
            table_name,
            sa.Column(
                "tenant_id",
                sa.Integer,
                nullable=True,
                comment="所属租户ID（冗余，加速按租户过滤）",
            ),
        )
        # 添加索引（加速按租户过滤查询）
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])
        # 添加外键约束
        op.create_foreign_key(
            constraint_name=f"fk_{table_name}_tenant_id",
            source_table=table_name,
            referent_table="tenants",
            local_cols=["tenant_id"],
            remote_cols=["id"],
            ondelete=ondelete,
        )


def downgrade() -> None:
    """回滚：移除 tenant_id 列 + 删除 tenants 表。"""
    # 1. 移除核心业务表的 tenant_id 列（外键 + 索引 + 列）
    for table_name, _ in reversed(_TENANT_AWARE_TABLES):
        op.drop_constraint(f"fk_{table_name}_tenant_id", table_name, type_="foreignkey")
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_column(table_name, "tenant_id")

    # 2. 删除 tenants 表
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
