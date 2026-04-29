"""
添加测试用例分类标签字段

Revision ID: add_test_case_category
Revises: add_project_file_ext_fields
Create Date: 2026-04-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_test_case_category'
down_revision = 'add_project_file_ext_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('test_cases', sa.Column('test_category', sa.String(100), nullable=True, comment='用例分类标签，多个用逗号分隔: ui_automation/manual/api_automation'))


def downgrade():
    op.drop_column('test_cases', 'test_category')