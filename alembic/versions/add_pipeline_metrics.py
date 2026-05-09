"""创建 pipeline_metrics 表 — FMEA 监控指标

表结构：
    pipeline_metrics(id, metric_name, value, project_id, iteration_id,
                     run_id, step_name, detail JSON, created_at)

索引：
    ix_pipeline_metrics_name_project : (metric_name, project_id)
    ix_pipeline_metrics_created_at   : created_at

Revision ID: add_pipeline_metrics
Revises: 20260501_add_posterior_quality_score
Create Date: 2026-05-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_pipeline_metrics'
down_revision = '20260501_add_posterior_quality_score'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pipeline_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_name', sa.String(64), nullable=False, comment='指标名（FMEA 枚举值）'),
        sa.Column('value', sa.Float(), nullable=False, server_default='1.0', comment='指标值'),
        sa.Column('project_id', sa.Integer(), nullable=True, comment='项目 ID'),
        sa.Column('iteration_id', sa.Integer(), nullable=True, comment='迭代 ID'),
        sa.Column('run_id', sa.Integer(), nullable=True, comment='PipelineRun ID'),
        sa.Column('step_name', sa.String(64), nullable=True, comment='Step 名称'),
        sa.Column('detail', sa.JSON(), nullable=True, comment='附加详情'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, comment='记录时间'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pipeline_metrics_name_project', 'pipeline_metrics', ['metric_name', 'project_id'])
    op.create_index('ix_pipeline_metrics_created_at', 'pipeline_metrics', ['created_at'])
    op.create_index(op.f('ix_pipeline_metrics_metric_name'), 'pipeline_metrics', ['metric_name'])
    op.create_index(op.f('ix_pipeline_metrics_project_id'), 'pipeline_metrics', ['project_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_pipeline_metrics_project_id'), table_name='pipeline_metrics')
    op.drop_index(op.f('ix_pipeline_metrics_metric_name'), table_name='pipeline_metrics')
    op.drop_index('ix_pipeline_metrics_created_at', table_name='pipeline_metrics')
    op.drop_index('ix_pipeline_metrics_name_project', table_name='pipeline_metrics')
    op.drop_table('pipeline_metrics')
