"""add project_members table

Revision ID: 20260728_add_project_members
Revises: 20260727_add_user_sessions
Create Date: 2026-07-28

新增 project_members 表，支撑项目级多角色成员体系（owner/admin/member/viewer），
替代原有单一的 Project.user_id 属主校验，实现细粒度项目权限控制（工作流B Task 8）。

表结构要点：
    project_members:
        - id         : BigInteger 自增主键
        - project_id : 项目 ID（外键关联 projects.id，ondelete=CASCADE）
        - user_id    : 用户 ID（外键关联 users.id，ondelete=CASCADE）
        - role       : 成员角色（owner/admin/member/viewer）
        - created_at / updated_at

索引设计：
    - uq_project_member (project_id, user_id) : 唯一约束，防止重复成员记录
    - ix_project_member_role (project_id, role) : 复合索引，按项目+角色查询

数据迁移：
    upgrade 时为每个已有项目的 user_id 插入一条 role='owner' 的成员记录，
    保证存量项目所有者自动获得 owner 角色，无缝衔接新的权限校验逻辑。

回滚策略：drop_table 即可，无数据损失（成员记录为新增数据）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers used by Alembic.
revision: str = "20260728_add_project_members"
down_revision: Union[str, None] = "20260727_add_user_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 project_members 表并迁移存量项目所有者为 owner 角色。"""
    op.create_table(
        "project_members",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="成员记录主键ID"),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="用户ID"),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member", comment="成员角色: owner/admin/member/viewer"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间（UTC）"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间（UTC）"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_members_project_id"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_project_members_user_id"), ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index(op.f("ix_project_members_project_id"), "project_members", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"], unique=False)
    op.create_index("ix_project_member_role", "project_members", ["project_id", "role"], unique=False)

    # 数据迁移：为每个已有项目的 user_id 插入 owner 成员记录
    op.execute(
        "INSERT INTO project_members (project_id, user_id, role, created_at, updated_at) "
        "SELECT id, user_id, 'owner', UTC_TIMESTAMP(), UTC_TIMESTAMP() FROM projects"
    )


def downgrade() -> None:
    """回滚：删除 project_members 表。"""
    op.drop_index("ix_project_member_role", table_name="project_members")
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_index(op.f("ix_project_members_project_id"), table_name="project_members")
    op.drop_table("project_members")
