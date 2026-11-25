"""add user_sessions table

Revision ID: 20260727_add_user_sessions
Revises: 20260727_add_agent_tables
Create Date: 2026-07-27

新增 user_sessions 表，记录每次登录后的会话元数据，支撑会话治理端点
（logout / logout-all / sessions / DELETE）与 SCIM deprovisioning 级联撤销
（add-security-compliance Task 2）。

表结构要点：
    - id              : Integer 自增主键
    - user_id         : 用户 ID（外键关联 users.id，ondelete=CASCADE）
    - refresh_jti     : refresh_token 的 jti 声明（唯一，黑名单匹配）
    - user_agent      : 客户端 User-Agent（设备识别）
    - ip_address      : 登录时客户端 IP（安全审计）
    - created_at      : 会话创建时间
    - last_active_at  : 最后活跃时间（刷新 access_token 时更新）
    - expires_at      : 会话过期时间（与 refresh_token exp 对齐）
    - revoked_at      : 会话撤销时间（NULL 表示有效，logout 时写入）

索引设计：
    - ix_user_sessions_user_id      : 单列索引，按用户维度检索会话
    - idx_user_active (user_id, revoked_at) : 复合索引，按用户+有效状态检索会话
    - idx_jti (refresh_jti)         : 单列索引，按 jti 检索会话（refresh 端点校验）
    - refresh_jti UNIQUE 约束        : 唯一约束，防止 jti 重复

存量数据兼容：新表无存量数据，所有 NOT NULL 列均带 server_default，
            保证后续若有数据回填场景时迁移稳定。

回滚策略：先 drop_constraint 释放外键与唯一约束（MySQL 要求外键列索引随约束释放），
        再 drop_index 各索引，最后 drop_table，无数据损失风险（表为新增）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers used by Alembic.
revision: str = "20260727_add_user_sessions"
down_revision: Union[str, None] = "20260727_add_agent_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 user_sessions 表与索引。"""
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="会话主键ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="用户ID"),
        sa.Column("refresh_jti", sa.String(length=128), nullable=False, comment="refresh_token 的 jti 声明（唯一标识）"),
        sa.Column("user_agent", sa.String(length=512), nullable=True, comment="客户端 User-Agent（用于设备识别）"),
        sa.Column("ip_address", sa.String(length=64), nullable=True, comment="登录时客户端 IP（用于安全审计）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="会话创建时间（UTC）"),
        sa.Column("last_active_at", sa.DateTime(), nullable=False, comment="最后活跃时间（UTC）"),
        sa.Column("expires_at", sa.DateTime(), nullable=False, comment="会话过期时间（与 refresh_token exp 对齐）"),
        sa.Column("revoked_at", sa.DateTime(), nullable=True, comment="会话撤销时间（NULL 表示有效）"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_sessions_user_id"), ondelete="CASCADE"),
        sa.UniqueConstraint("refresh_jti", name=op.f("uq_user_sessions_refresh_jti")),
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.create_index("idx_user_active", "user_sessions", ["user_id", "revoked_at"], unique=False)
    op.create_index("idx_jti", "user_sessions", ["refresh_jti"], unique=False)


def downgrade() -> None:
    """回滚：先删除外键与唯一约束，再删除索引与表。"""
    op.drop_constraint(op.f("uq_user_sessions_refresh_jti"), "user_sessions", type_="unique")
    op.drop_constraint(op.f("fk_user_sessions_user_id"), "user_sessions", type_="foreignkey")
    op.drop_index("idx_jti", table_name="user_sessions")
    op.drop_index("idx_user_active", table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_table("user_sessions")
