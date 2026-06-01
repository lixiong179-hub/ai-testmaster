"""新增资料融合生成批次表：generation_batches, generation_batch_saves

1. generation_batches 表：
   - id, batch_no, project_id FK, user_id FK, entry_type, scenario_type,
     generation_strategy, status, requirement_file_ids_json, test_point_ids_json,
     ui_screen_ids_json, context_stats_json, warnings_json, evidence_refs_json,
     quality_summary_json, client_request_id, created_at, updated_at
   - 索引 ix_gen_batch_project_created, ix_gen_batch_project_status,
     ix_gen_batch_user_created, batch_no unique

2. generation_batch_saves 表：
   - id, batch_id FK, idempotency_key, save_mode, request_hash,
     result_json, created_at
   - 唯一索引 ix_gen_batch_save_unique (batch_id, idempotency_key)

Revision ID: add_generation_batch
Revises: 20260530_add_snapshot_version_id
Create Date: 2026-06-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_generation_batch'
down_revision = '20260530_add_snapshot_version_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'generation_batches',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_no', sa.String(40), nullable=False, comment='人类可读批次号'),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, comment='项目ID'),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='创建人ID'),
        sa.Column('entry_type', sa.String(40), nullable=False, server_default='NEW_FEATURE_GENERATION', comment='任务入口类型'),
        sa.Column('scenario_type', sa.String(60), nullable=False, comment='资料组合场景'),
        sa.Column('generation_strategy', sa.String(80), nullable=False, comment='生成策略'),
        sa.Column('status', sa.String(30), nullable=False, server_default='created', comment='批次状态'),
        sa.Column('requirement_file_ids_json', sa.JSON(), nullable=False, comment='需求文件ID列表'),
        sa.Column('test_point_ids_json', sa.JSON(), nullable=False, comment='测试点ID列表'),
        sa.Column('ui_screen_ids_json', sa.JSON(), nullable=False, comment='UI页面ID列表'),
        sa.Column('context_stats_json', sa.JSON(), nullable=False, comment='上下文统计'),
        sa.Column('warnings_json', sa.JSON(), nullable=False, comment='结构化warning'),
        sa.Column('evidence_refs_json', sa.JSON(), nullable=False, comment='来源依据'),
        sa.Column('quality_summary_json', sa.JSON(), nullable=False, comment='质量摘要'),
        sa.Column('client_request_id', sa.String(80), nullable=True, comment='前端请求ID'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_generation_batches_id', 'generation_batches', ['id'])
    op.create_index('ix_generation_batches_batch_no', 'generation_batches', ['batch_no'], unique=True)
    op.create_index('ix_generation_batches_project_id', 'generation_batches', ['project_id'])
    op.create_index('ix_generation_batches_user_id', 'generation_batches', ['user_id'])
    op.create_index('ix_generation_batches_entry_type', 'generation_batches', ['entry_type'])
    op.create_index('ix_generation_batches_scenario_type', 'generation_batches', ['scenario_type'])
    op.create_index('ix_generation_batches_generation_strategy', 'generation_batches', ['generation_strategy'])
    op.create_index('ix_generation_batches_status', 'generation_batches', ['status'])
    op.create_index('ix_gen_batch_project_created', 'generation_batches', ['project_id', 'created_at'])
    op.create_index('ix_gen_batch_project_status', 'generation_batches', ['project_id', 'status'])
    op.create_index('ix_gen_batch_user_created', 'generation_batches', ['user_id', 'created_at'])

    op.create_table(
        'generation_batch_saves',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('generation_batches.id', ondelete='CASCADE'), nullable=False, comment='批次ID'),
        sa.Column('idempotency_key', sa.String(100), nullable=False, comment='保存幂等键'),
        sa.Column('save_mode', sa.String(30), nullable=False, comment='保存模式'),
        sa.Column('request_hash', sa.String(64), nullable=True, comment='请求体hash'),
        sa.Column('result_json', sa.JSON(), nullable=False, comment='首次保存结果'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_generation_batch_saves_id', 'generation_batch_saves', ['id'])
    op.create_index('ix_generation_batch_saves_batch_id', 'generation_batch_saves', ['batch_id'])
    op.create_index('ix_gen_batch_save_unique', 'generation_batch_saves', ['batch_id', 'idempotency_key'], unique=True)


def downgrade() -> None:
    op.drop_table('generation_batch_saves')
    op.drop_table('generation_batches')
