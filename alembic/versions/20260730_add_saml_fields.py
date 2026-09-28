"""add saml sso fields to users table

Revision ID: 20260730_add_saml_fields
Revises: 20260730_add_oidc_fields
Create Date: 2026-07-30

Phase 3 Task 4: SAML 2.0 SSO SP 实现 — 用户表新增 saml_nameid/saml_issuer/
saml_provider/saml_session_index 字段，用于绑定外部 SAML IdP 账号与本地账号的关联关系。

迁移内容：
    1. users 表新增 saml_nameid（NameID）、saml_issuer（IdP EntityID）、
       saml_provider（IdP 标识）、saml_session_index（SessionIndex，用于 SLO）
    2. 创建 (saml_issuer, saml_nameid) 联合唯一索引，防止同一 IdP 同一 NameID 重复绑定
    3. 单独为 saml_provider / saml_session_index 创建索引，便于按 IdP 分类查询与 SLO 定位

设计说明：
    - 四字段均可为 NULL（兼容本地账号用户）
    - 联合唯一索引确保同一 IdP 的同一 NameID 仅能绑定一个本地账号
    - saml_issuer + saml_nameid 是 SAML 规范中识别外部账号的标准组合
    - saml_session_index 用于 Single Logout（SLO）时定位 IdP 会话
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260730_add_saml_fields"
down_revision = "20260730_add_oidc_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加 SAML SSO 字段到 users 表。"""
    op.add_column(
        "users",
        sa.Column("saml_nameid", sa.String(255), nullable=True, comment="SAML NameID（IdP 返回的主体标识）"),
    )
    op.add_column(
        "users",
        sa.Column("saml_issuer", sa.String(255), nullable=True, comment="SAML issuer（IdP EntityID）"),
    )
    op.add_column(
        "users",
        sa.Column("saml_provider", sa.String(50), nullable=True, comment="SAML provider 标识"),
    )
    op.add_column(
        "users",
        sa.Column(
            "saml_session_index",
            sa.String(255),
            nullable=True,
            comment="SAML SessionIndex（用于 SLO）",
        ),
    )
    # 单列索引（便于按 provider / nameid / issuer / session_index 单独查询）
    op.create_index("ix_users_saml_nameid", "users", ["saml_nameid"])
    op.create_index("ix_users_saml_issuer", "users", ["saml_issuer"])
    op.create_index("ix_users_saml_provider", "users", ["saml_provider"])
    op.create_index("ix_users_saml_session_index", "users", ["saml_session_index"])
    # 联合唯一索引：同一 IdP 的同一 NameID 仅能绑定一个本地账号
    # MySQL 注意：NULL 在唯一索引中互不相等，故未绑定用户（NULL）不会冲突
    op.create_index(
        "uq_users_saml_issuer_nameid",
        "users",
        ["saml_issuer", "saml_nameid"],
        unique=True,
    )


def downgrade() -> None:
    """回滚 SAML SSO 字段。"""
    op.drop_index("uq_users_saml_issuer_nameid", table_name="users")
    op.drop_index("ix_users_saml_session_index", table_name="users")
    op.drop_index("ix_users_saml_provider", table_name="users")
    op.drop_index("ix_users_saml_issuer", table_name="users")
    op.drop_index("ix_users_saml_nameid", table_name="users")
    op.drop_column("users", "saml_session_index")
    op.drop_column("users", "saml_provider")
    op.drop_column("users", "saml_issuer")
    op.drop_column("users", "saml_nameid")
