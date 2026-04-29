"""
创建 ai_call_log 表

表结构：
    id, run_id FK(pipeline_runs.id, SET NULL), step_name, model,
    prompt_tokens, completion_tokens, cost_usd, latency_ms,
    status, error_message, created_at

Revision ID: add_ai_call_log
Revises: add_pipeline_tables
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_ai_call_log'
down_revision = 'add_pipeline_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ai_call_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=True, comment='关联运行ID'),
        sa.Column('step_name', sa.String(64), nullable=True, comment='Step 名称'),
        sa.Column('model', sa.String(64), nullable=False, comment='使用的AI模型'),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0', comment='输入Token数'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0', comment='输出Token数'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0', comment='调用成本（美元）'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0', comment='调用耗时（毫秒）'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success', comment='状态: success/failed'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['run_id'], ['pipeline_runs.id'],
            ondelete='SET NULL', name='fk_ai_call_log_run_id',
        ),
    )
    op.create_index('ix_ai_call_log_run_id', 'ai_call_log', ['run_id'])


def downgrade():
    op.drop_index('ix_ai_call_log_run_id', table_name='ai_call_log')
    op.drop_table('ai_call_log')
