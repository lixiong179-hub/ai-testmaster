"""
增强 Iteration 模型以支持流水线上下文，创建 iteration_inputs 表

1. iterations 表新增字段：
   - base_iteration_id (FK → iterations.id, SET NULL) : 基线迭代
   - created_by (FK → users.id, SET NULL) : 创建人
   - finalized_at (DateTime, nullable) : 定稿时间

2. iterations.status 约束从 planning/active/completed/archived
   改为 draft/in_pipeline/in_review/finalized/archived，
   并将默认值从 'planning' 改为 'draft'。
   现有数据通过映射迁移：planning→draft, active→in_pipeline, completed→finalized

3. 新建 iteration_inputs 表：
   - id, iteration_id FK, kind, file_id FK NULL, payload JSON NULL, content_hash, uploaded_at
   - 索引 (iteration_id, kind)
   - CHECK 约束 kind IN (prd, prototype, xmind, testpoint, supplement_form)

注意：先 drop 旧 CHECK constraint 再迁移数据，避免 MySQL 8.0.16+ 约束校验失败。

Revision ID: add_iter_pipeline
Revises: change_lc_default_draft
Create Date: 2026-04-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_iter_pipeline'
down_revision = 'change_lc_default_draft'
branch_labels = None
depends_on = None


def upgrade():
    # 1. 先删除旧约束，再迁移数据（避免 MySQL 8.0.16+ CHECK 校验）
    op.drop_constraint('ck_iteration_status', 'iterations', type_='check')

    # 2. 迁移现有状态值：planning→draft, active→in_pipeline, completed→finalized
    op.execute(
        "UPDATE iterations SET status = 'draft' WHERE status = 'planning'"
    )
    op.execute(
        "UPDATE iterations SET status = 'in_pipeline' WHERE status = 'active'"
    )
    op.execute(
        "UPDATE iterations SET status = 'finalized' WHERE status = 'completed'"
    )

    # 3. 修改默认值
    op.alter_column(
        'iterations', 'status',
        existing_type=sa.String(20),
        nullable=False,
        server_default='draft',
        existing_server_default='planning',
    )

    # 4. 添加新约束
    op.create_check_constraint(
        'ck_iteration_status',
        'iterations',
        "status IN ('draft', 'in_pipeline', 'in_review', 'finalized', 'archived')"
    )

    # 5. 新增流水线上下文字段
    op.add_column('iterations', sa.Column(
        'base_iteration_id', sa.Integer(),
        nullable=True, comment='基线迭代ID，用于跨迭代对比'
    ))
    op.add_column('iterations', sa.Column(
        'created_by', sa.Integer(),
        nullable=True, comment='创建人ID'
    ))
    op.add_column('iterations', sa.Column(
        'finalized_at', sa.DateTime(),
        nullable=True, comment='定稿时间'
    ))

    op.create_foreign_key(
        'fk_iterations_base_iteration_id', 'iterations', 'iterations',
        ['base_iteration_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_iterations_created_by', 'iterations', 'users',
        ['created_by'], ['id'], ondelete='SET NULL',
    )

    # 6. 创建 iteration_inputs 表
    op.create_table(
        'iteration_inputs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('iteration_id', sa.Integer(), nullable=False, comment='关联迭代ID'),
        sa.Column('kind', sa.String(30), nullable=False, comment='输入类型: prd/prototype/xmind/testpoint/supplement_form'),
        sa.Column('file_id', sa.Integer(), nullable=True, comment='关联项目文件ID'),
        sa.Column('payload', sa.JSON(), nullable=True, comment='非文件型输入的JSON载荷'),
        sa.Column('content_hash', sa.String(64), nullable=False, comment='输入内容哈希，用于幂等校验'),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), comment='上传时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['iteration_id'], ['iterations.id'],
            ondelete='CASCADE', name='fk_iteration_inputs_iteration_id',
        ),
        sa.ForeignKeyConstraint(
            ['file_id'], ['project_files.id'],
            ondelete='SET NULL', name='fk_iteration_inputs_file_id',
        ),
        sa.CheckConstraint(
            "kind IN ('prd', 'prototype', 'xmind', 'testpoint', 'supplement_form')",
            name='ck_iteration_input_kind',
        ),
    )
    op.create_index(
        'ix_iteration_input_iter_kind', 'iteration_inputs',
        ['iteration_id', 'kind'],
    )


def downgrade():
    # 1. 删除 iteration_inputs 表
    op.drop_index('ix_iteration_input_iter_kind', table_name='iteration_inputs')
    op.drop_table('iteration_inputs')

    # 2. 删除新增字段
    op.drop_constraint('fk_iterations_created_by', 'iterations', type_='foreignkey')
    op.drop_constraint('fk_iterations_base_iteration_id', 'iterations', type_='foreignkey')
    op.drop_column('iterations', 'finalized_at')
    op.drop_column('iterations', 'created_by')
    op.drop_column('iterations', 'base_iteration_id')

    # 3. 先 drop 当前约束，再回退状态值（避免约束校验）
    op.drop_constraint('ck_iteration_status', 'iterations', type_='check')

    # 4. 回退状态值
    op.execute(
        "UPDATE iterations SET status = 'planning' WHERE status = 'draft'"
    )
    op.execute(
        "UPDATE iterations SET status = 'active' WHERE status = 'in_pipeline'"
    )
    op.execute(
        "UPDATE iterations SET status = 'completed' WHERE status = 'finalized'"
    )
    op.execute(
        "UPDATE iterations SET status = 'completed' WHERE status = 'in_review'"
    )

    # 5. 恢复默认值
    op.alter_column(
        'iterations', 'status',
        existing_type=sa.String(20),
        nullable=False,
        server_default='planning',
        existing_server_default='draft',
    )

    # 6. 重建旧约束
    op.create_check_constraint(
        'ck_iteration_status',
        'iterations',
        "status IN ('planning', 'active', 'completed', 'archived')"
    )
