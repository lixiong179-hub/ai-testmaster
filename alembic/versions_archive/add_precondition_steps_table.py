"""
添加前置条件步骤表和element_locators前置条件步骤关联

Revision ID: add_precondition_steps_table
Revises: ('add_test_case_category', 'add_unique_step_id_to_element_locators')
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_precondition_steps_table'
down_revision = ('add_test_case_category', 'add_unique_step_id_to_element_locators')
branch_labels = None
depends_on = None


def upgrade():
    """创建前置条件步骤表，并在element_locators表中添加precondition_step_id列"""
    # 1. 创建 test_case_precondition_steps 表
    op.create_table(
        'test_case_precondition_steps',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('test_case_id', sa.Integer(), sa.ForeignKey('test_cases.id', ondelete='CASCADE'), nullable=False, index=True, comment='关联测试用例ID'),
        sa.Column('step_number', sa.Integer(), nullable=False, comment='步骤序号'),
        sa.Column('action', sa.Text(), nullable=False, comment='操作步骤'),
        sa.Column('expected_result', sa.Text(), nullable=False, server_default='', comment='预期结果'),
        sa.Column('create_time', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.Column('has_locator', sa.Integer(), nullable=False, server_default='0', comment='是否已记录元素定位：0否/1是'),
        sa.Column('locator_status', sa.String(20), nullable=False, server_default='pending', comment='定位状态：pending/recorded/failed'),
        sa.Column('action_type', sa.String(20), nullable=True, comment='操作类型：click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress'),
        sa.Column('input_value', sa.String(500), nullable=True, comment='输入值（仅input类型步骤）'),
        sa.Column('target_element', sa.String(200), nullable=True, comment='目标元素描述'),
        mysql_charset='utf8mb4',
        mysql_engine='InnoDB',
    )

    # 2. 在 element_locators 表中添加 precondition_step_id 列
    op.add_column(
        'element_locators',
        sa.Column('precondition_step_id', sa.Integer(), nullable=True, comment='关联前置条件步骤ID')
    )
    op.create_index('ix_element_locators_precondition_step_id', 'element_locators', ['precondition_step_id'])
    op.create_foreign_key(
        'fk_element_locators_precondition_step_id',
        'element_locators',
        'test_case_precondition_steps',
        ['precondition_step_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade():
    """回滚：删除element_locators的precondition_step_id列，删除test_case_precondition_steps表"""
    # 1. 删除 element_locators 表中的外键和列
    op.drop_constraint('fk_element_locators_precondition_step_id', 'element_locators', type_='foreignkey')
    op.drop_index('ix_element_locators_precondition_step_id', table_name='element_locators')
    op.drop_column('element_locators', 'precondition_step_id')

    # 2. 删除 test_case_precondition_steps 表
    op.drop_table('test_case_precondition_steps')
