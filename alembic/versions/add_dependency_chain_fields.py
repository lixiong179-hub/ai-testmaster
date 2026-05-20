"""添加测试用例依赖链字段和API前置准备字段

新增 test_cases 表字段:
    - depends_on: 依赖的主干用例标题（分支/异常用例依赖主干用例）
    - anchor_step: 依赖主干用例的步骤号（锚点步骤）
    - fallback_steps: 降级导航步骤JSON（快照不可用时重放这些步骤）
    - setup_api_calls: API前置准备JSON（B端用例通过API直接创建数据状态）

Revision ID: add_dependency_chain_fields
Revises: rename_skipped_to_blocked
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_dependency_chain_fields'
down_revision = 'rename_skipped_to_blocked'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'test_cases',
        sa.Column('depends_on', sa.String(255), nullable=True, comment='依赖的主干用例标题'),
    )
    op.add_column(
        'test_cases',
        sa.Column('anchor_step', sa.Integer(), nullable=True, comment='依赖主干用例的步骤号'),
    )
    op.add_column(
        'test_cases',
        sa.Column('fallback_steps', sa.Text(), nullable=True, comment='降级导航步骤JSON'),
    )
    op.add_column(
        'test_cases',
        sa.Column('setup_api_calls', sa.Text(), nullable=True, comment='API前置准备JSON'),
    )
    # 为 depends_on 添加索引，加速依赖图构建时的按标题查询
    op.create_index(
        'ix_test_cases_depends_on', 'test_cases', ['depends_on'],
    )


def downgrade():
    op.drop_index('ix_test_cases_depends_on', table_name='test_cases')
    op.drop_column('test_cases', 'setup_api_calls')
    op.drop_column('test_cases', 'fallback_steps')
    op.drop_column('test_cases', 'anchor_step')
    op.drop_column('test_cases', 'depends_on')
