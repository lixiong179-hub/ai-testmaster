"""change project_files.content to MEDIUMTEXT

MySQL TEXT 类型最大 65,535 字节，200K 中文字符（UTF-8 约 600KB）
写入时会报 Data too long for column 错误。
将 project_files.content 从 TEXT 改为 MEDIUMTEXT（最大 16MB）以支持大文件内容提取。

Revision ID: 20260605_content_mediumtext
Revises: 20260604_merge_heads
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT

# revision identifiers, used by Alembic.
revision = "20260605_content_mediumtext"
down_revision = "20260604_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "project_files", "content",
        existing_type=sa.Text(),
        type_=MEDIUMTEXT(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "project_files", "content",
        existing_type=MEDIUMTEXT(),
        type_=sa.Text(),
        existing_nullable=True,
    )
