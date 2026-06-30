"""nullable legacy columns in test_case_versions

Revision ID: 20260625_nullable_case_id
Revises: 20260625_add_project_title_index
Create Date: 2026-06-25

test_case_versions 表历史遗留 case_id、data_json 列（NOT NULL 无默认值），
模型已重构为 test_case_id + snapshot_data，但旧列未迁移，导致 INSERT 时
因旧列无值触发 "Field '...' doesn't have a default value" 错误，
使用例更新接口返回 500。

修复策略：将 case_id、data_json 改为 nullable，兼容旧数据并消除插入阻断。
回滚策略：恢复为 NOT NULL（仅在确认无 NULL 数据时安全执行）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_nullable_case_id"
down_revision: Union[str, None] = "20260625_add_project_title_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 test_case_versions 旧列 case_id、data_json 改为 nullable，消除插入阻断。"""
    op.alter_column(
        "test_case_versions",
        "case_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "test_case_versions",
        "data_json",
        existing_type=sa.JSON(),
        nullable=True,
    )


def downgrade() -> None:
    """恢复 case_id、data_json 为 NOT NULL。"""
    op.alter_column(
        "test_case_versions",
        "data_json",
        existing_type=sa.JSON(),
        nullable=False,
    )
    op.alter_column(
        "test_case_versions",
        "case_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
