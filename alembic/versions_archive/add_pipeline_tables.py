"""
创建 Pipeline 存储表：pipeline_runs, pipeline_steps, artifacts

1. pipeline_runs 表：
   - id, iteration_id FK, input_hash, pipeline_version, status,
     started_at, finished_at, error
   - 索引 ix_pipeline_run_iteration_id
   - CHECK 约束 ck_pipeline_run_status

2. pipeline_steps 表：
   - id, run_id FK, step_name, step_version, status, cache_key,
     input_artifact_ids JSON, output_artifact_ids JSON,
     started_at, finished_at, error, retried_count, degraded
   - CHECK 约束 ck_pipeline_step_status

3. artifacts 表：
   - id, run_id FK, kind, schema_version, payload JSON, confidence,
     provenance JSON, content_hash, created_at
   - 唯一约束 uq_artifact_content_hash 防重复落库
   - 索引 ix_artifact_content_hash

Revision ID: add_pipeline_tables
Revises: add_iter_pipeline
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_pipeline_tables'
down_revision = 'add_iter_pipeline'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 创建 pipeline_runs 表
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('iteration_id', sa.Integer(), nullable=False, comment='关联迭代ID'),
        sa.Column('input_hash', sa.String(64), nullable=False, comment='输入内容哈希，用于幂等校验'),
        sa.Column('pipeline_version', sa.String(32), nullable=False, server_default='1.0', comment='Pipeline 版本号'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending',
                  comment='状态: pending/running/waiting_for_user/completed/failed/cancelled'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='开始执行时间'),
        sa.Column('finished_at', sa.DateTime(), nullable=True, comment='执行完成时间'),
        sa.Column('error', sa.Text(), nullable=True, comment='错误信息'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['iteration_id'], ['iterations.id'],
            ondelete='CASCADE', name='fk_pipeline_runs_iteration_id',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'waiting_for_user', 'completed', 'failed', 'cancelled')",
            name='ck_pipeline_run_status',
        ),
    )
    op.create_index('ix_pipeline_run_iteration_id', 'pipeline_runs', ['iteration_id'])

    # 2. 创建 pipeline_steps 表
    op.create_table(
        'pipeline_steps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False, comment='关联运行ID'),
        sa.Column('step_name', sa.String(64), nullable=False, comment='Step 名称'),
        sa.Column('step_version', sa.String(32), nullable=False, server_default='1.0', comment='Step 版本号'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending',
                  comment='状态: pending/running/done/failed/skipped/degraded'),
        sa.Column('cache_key', sa.String(64), nullable=True, comment='缓存键，用于幂等跳过'),
        sa.Column('input_artifact_ids', sa.JSON(), nullable=True, comment='输入产物ID列表'),
        sa.Column('output_artifact_ids', sa.JSON(), nullable=True, comment='输出产物ID列表'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='开始执行时间'),
        sa.Column('finished_at', sa.DateTime(), nullable=True, comment='执行完成时间'),
        sa.Column('error', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('retried_count', sa.Integer(), nullable=False, server_default='0', comment='重试次数'),
        sa.Column('degraded', sa.Boolean(), nullable=False, server_default=sa.text('0'), comment='是否降级完成'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['run_id'], ['pipeline_runs.id'],
            ondelete='CASCADE', name='fk_pipeline_steps_run_id',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed', 'skipped', 'degraded')",
            name='ck_pipeline_step_status',
        ),
    )
    op.create_index('ix_pipeline_step_cache_key', 'pipeline_steps', ['cache_key'])

    # 3. 创建 artifacts 表
    op.create_table(
        'artifacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False, comment='关联运行ID'),
        sa.Column('kind', sa.String(64), nullable=False, comment='产物类型'),
        sa.Column('schema_version', sa.String(32), nullable=False, server_default='1.0', comment='产物 schema 版本'),
        sa.Column('payload', sa.JSON(), nullable=True, comment='产物 JSON 载荷'),
        sa.Column('confidence', sa.Float(), nullable=True, comment='置信度分数'),
        sa.Column('provenance', sa.JSON(), nullable=True, comment='产物来源信息'),
        sa.Column('content_hash', sa.String(64), nullable=False, comment='产物内容哈希，防重复落库'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['run_id'], ['pipeline_runs.id'],
            ondelete='CASCADE', name='fk_artifacts_run_id',
        ),
        sa.UniqueConstraint('content_hash', name='uq_artifact_content_hash'),
    )


def downgrade():
    # 反序删除
    op.drop_table('artifacts')

    op.drop_index('ix_pipeline_step_cache_key', table_name='pipeline_steps')
    op.drop_table('pipeline_steps')

    op.drop_index('ix_pipeline_run_iteration_id', table_name='pipeline_runs')
    op.drop_table('pipeline_runs')
