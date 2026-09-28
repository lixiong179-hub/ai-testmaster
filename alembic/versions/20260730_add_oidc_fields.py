"""add oidc sso fields to users table

Revision ID: 20260730_add_oidc_fields
Revises: 20260730_add_tenant_isolation
Create Date: 2026-07-30

Phase 3 Task 5: OIDC SSO 适配 — 用户表新增 oidc_sub/oidc_issuer/oidc_provider 字段，
用于绑定外部 IdP 账号与本地账号的关联关系。

迁移内容：
    1. users 表新增 oidc_sub（OIDC subject）、oidc_issuer（签发方 URL）、oidc_provider（IdP 标识）
    2. 创建 (oidc_issuer, oidc_sub) 联合唯一索引，防止同一 IdP 同一 subject 重复绑定
    3. 单独为 oidc_provider 创建索引，便于按 IdP 分类查询

设计说明：
    - 三字段均可为 NULL（兼容本地账号用户）
    - 联合唯一索引确保同一 IdP 的同一 subject 仅能绑定一个本地账号
    - oidc_issuer + oidc_sub 是 OIDC 规范中识别外部账号的标准组合
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260730_add_oidc_fields"
down_revision = "20260730_add_tenant_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 OIDC SSO 字段到 users 表。"""
    op.add_column(
        "users",
        sa.Column("oidc_sub", sa.String(255), nullable=True, comment="OIDC subject（IdP 返回的 sub）"),
    )
    op.add_column(
        "users",
        sa.Column("oidc_issuer", sa.String(255), nullable=True, comment="OIDC issuer（IdP 签发方 URL）"),
    )
    op.add_column(
        "users",
        sa.Column("oidc_provider", sa.String(50), nullable=True, comment="OIDC provider 标识"),
    )
    # 单列索引（便于按 provider / sub / issuer 单独查询）
    op.create_index("ix_users_oidc_sub", "users", ["oidc_sub"])
    op.create_index("ix_users_oidc_issuer", "users", ["oidc_issuer"])
    op.create_index("ix_users_oidc_provider", "users", ["oidc_provider"])
    # 联合唯一索引：同一 IdP 的同一 subject 仅能绑定一个本地账号
    # MySQL 注意：NULL 在唯一索引中互不相等，故未绑定用户（NULL）不会冲突
    op.create_index(
        "uq_users_oidc_issuer_sub",
        "users",
        ["oidc_issuer", "oidc_sub"],
        unique=True,
    )


def downgrade() -> None:
    """回滚 OIDC SSO 字段。"""
    op.drop_index("uq_users_oidc_issuer_sub", table_name="users")
    op.drop_index("ix_users_oidc_provider", table_name="users")
    op.drop_index("ix_users_oidc_issuer", table_name="users")
    op.drop_index("ix_users_oidc_sub", table_name="users")
    op.drop_column("users", "oidc_provider")
    op.drop_column("users", "oidc_issuer")
    op.drop_column("users", "oidc_sub")
