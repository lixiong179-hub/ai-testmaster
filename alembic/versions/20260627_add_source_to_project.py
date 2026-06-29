"""add source column to projects

Revision ID: 20260627_add_source_to_project
Revises: 20260625_nullable_case_id
Create Date: 2026-06-27

为 projects 表新增 source 列，标识项目创建来源：
    - manual          : 手动建项（默认，兼容存量数据）
    - url_quick_test  : 网址驱动快速测试自动建项

业务用途：支撑"网址驱动快速测试"特性（url-driven-quick-test）按来源筛选
历史快速测试项目，区分传统手动建项与一键 URL 建项。

存量数据兼容：server_default='manual' 保证存量行回填默认值，避免 NOT NULL
约束导致迁移失败。

回滚策略：drop 索引后 drop 列，无数据损失（source 仅元信息标识）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers used by Alembic.
revision: str = "20260627_add_source_to_project"
down_revision: Union[str, None] = "20260625_nullable_case_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 projects.source 列并建立按来源筛选索引。"""
    op.add_column(
        "projects",
        sa.Column(
            "source",
            sa.String(64),
            nullable=False,
            server_default="manual",
            comment="项目来源: manual=手动建项, url_quick_test=网址驱动快速测试",
        ),
    )
    op.create_index("ix_projects_source", "projects", ["source"], unique=False)


def downgrade() -> None:
    """回滚：删除 projects.source 列及其索引。"""
    op.drop_index("ix_projects_source", table_name="projects")
    op.drop_column("projects", "source")
