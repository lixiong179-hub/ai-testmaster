"""
添加项目文件扩展字段和资源类型

Revision ID: add_project_file_ext_fields
Revises: 20240328_add_element_locator
Create Date: 2026-04-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_project_file_ext_fields'
down_revision = '20240328_add_element_locator'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 resource_type 字段
    op.add_column('project_files', sa.Column('resource_type', sa.String(50), nullable=True, server_default='other', comment='资源类型: requirement/ui_mockup/api_doc/test_data/other'))
    # 添加 content 字段（文本内容提取）
    op.add_column('project_files', sa.Column('content', sa.Text(), nullable=True, comment='从文件提取的文本内容'))
    # 添加 extract_status 字段
    op.add_column('project_files', sa.Column('extract_status', sa.String(20), nullable=False, server_default='pending', comment='内容提取状态: pending/processing/completed/failed'))
    # 添加 extract_error 字段
    op.add_column('project_files', sa.Column('extract_error', sa.Text(), nullable=True, comment='提取失败原因'))
    # 添加 extracted_at 字段
    op.add_column('project_files', sa.Column('extracted_at', sa.DateTime(), nullable=True, comment='内容提取时间'))
    # 添加 description 字段
    op.add_column('project_files', sa.Column('description', sa.Text(), nullable=True, comment='文件描述'))
    # 添加 is_active 字段（软删除）
    op.add_column('project_files', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1', comment='是否启用'))
    # 添加 linked_case_count 字段
    op.add_column('project_files', sa.Column('linked_case_count', sa.Integer(), nullable=False, server_default='0', comment='关联测试用例数量'))


def downgrade():
    op.drop_column('project_files', 'linked_case_count')
    op.drop_column('project_files', 'is_active')
    op.drop_column('project_files', 'description')
    op.drop_column('project_files', 'extracted_at')
    op.drop_column('project_files', 'extract_error')
    op.drop_column('project_files', 'extract_status')
    op.drop_column('project_files', 'content')
    op.drop_column('project_files', 'resource_type')