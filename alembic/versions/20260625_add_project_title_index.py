"""add (project_id, title) index to test_cases

Revision ID: 20260625_add_project_title_index
Revises: 20260625_add_quality_grade
Create Date: 2026-06-25

为 test_cases 表添加 (project_id, title) 非唯一复合索引，支撑两处用途：
    1. 加速 _case_title_exists 的存在性检查查询
    2. 配合 with_for_update() 利用 InnoDB REPEATABLE READ 的 gap lock，
       使 check-then-insert 原子化，消除标题并发竞态（R3 修复）

非唯一索引说明：
    MySQL 不支持 partial index（WHERE 子句过滤的唯一索引），且现有库存在
    2590 行历史重复 title 数据无法直接添加唯一约束。改用非唯一索引 + 行级
    锁方案，仅防止新增重复，不触碰历史数据。

回滚策略: drop_index，无数据影响。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_add_project_title_index"
down_revision: Union[str, None] = "20260625_add_quality_grade"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 (project_id, title) 复合索引。"""
    op.create_index(
        "ix_test_cases_project_title",
        "test_cases",
        ["project_id", "title"],
        unique=False,
    )


def downgrade() -> None:
    """删除 (project_id, title) 复合索引。"""
    op.drop_index("ix_test_cases_project_title", table_name="test_cases")
