"""
添加视图相关字段到test_steps表

Revision ID: add_view_fields_to_test_steps
Revises: 
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'add_view_fields_to_test_steps'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """添加视图相关字段"""
    # 添加业务视图和技术视图字段
    op.add_column('test_steps', sa.Column('is_business_view', sa.Integer(), nullable=False, server_default='1', comment='是否在业务视图显示：0隐藏/1显示'))
    op.add_column('test_steps', sa.Column('is_technical_view', sa.Integer(), nullable=False, server_default='1', comment='是否在技术视图显示：0隐藏/1显示'))
    
    # 添加元素定位相关字段
    op.add_column('test_steps', sa.Column('has_locator', sa.Integer(), nullable=False, server_default='0', comment='是否已记录元素定位：0否/1是'))
    op.add_column('test_steps', sa.Column('locator_status', sa.String(length=20), nullable=False, server_default='pending', comment='定位状态：pending/recorded/failed'))
    
    # 更新element_locators表的外键关系
    op.alter_column('element_locators', 'step_id',
                    existing_type=sa.Integer(),
                    nullable=False)
    op.create_foreign_key('fk_element_locators_test_steps', 'element_locators', 'test_steps', ['step_id'], ['id'], ondelete='CASCADE')


def downgrade():
    """回滚视图相关字段"""
    # 删除外键
    op.drop_constraint('fk_element_locators_test_steps', 'element_locators', type_='foreignkey')
    
    # 删除字段
    op.drop_column('test_steps', 'locator_status')
    op.drop_column('test_steps', 'has_locator')
    op.drop_column('test_steps', 'is_technical_view')
    op.drop_column('test_steps', 'is_business_view')
