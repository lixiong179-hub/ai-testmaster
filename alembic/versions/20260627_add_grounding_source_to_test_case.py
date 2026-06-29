"""add grounding_source column to test_cases

Revision ID: 20260627_add_grounding_source_to_test_case
Revises: 20260627_add_source_to_project
Create Date: 2026-06-27

为 test_cases 表新增 grounding_source 列，标识用例步骤元素锚定的依据：
    - dom_snapshot  : 网址驱动快速测试基于站点探索真实 DOM 快照生成（禁编造）
    - manual        : 人工填写步骤
    - NULL          : 未锚定（兼容存量数据，不强制回填）

业务用途：支撑"网址驱动快速测试"特性（url-driven-quick-test Task 6）的元素
锚定溯源，区分 AI 基于真实 DOM 生成的用例与人工/其他来源用例，配合
element_verified_ratio 量化元素锚定质量。

存量数据兼容：nullable=True 不回填，保证存量行迁移不失败。

回滚策略：drop 索引后 drop 列，无数据损失（grounding_source 仅元信息标识）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers used by Alembic.
revision: str = "20260627_add_grounding_source_to_test_case"
down_revision: Union[str, None] = "20260627_add_source_to_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 test_cases.grounding_source 列并建立按来源筛选索引。"""
    op.add_column(
        "test_cases",
        sa.Column(
            "grounding_source",
            sa.String(32),
            nullable=True,
            comment="元素锚定来源: dom_snapshot/manual",
        ),
    )
    op.create_index(
        "ix_test_cases_grounding_source",
        "test_cases",
        ["grounding_source"],
        unique=False,
    )


def downgrade() -> None:
    """回滚：删除 test_cases.grounding_source 列及其索引。"""
    op.drop_index("ix_test_cases_grounding_source", table_name="test_cases")
    op.drop_column("test_cases", "grounding_source")
