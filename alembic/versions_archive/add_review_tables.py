"""创建评审表：iteration_review, review_decision, review_lock

1. iteration_review 表：
   - id, iteration_id FK, kind, status, created_at, finalized_at, finalized_by FK
   - 索引 ix_iteration_review_iteration_id, ix_iteration_review_status

2. review_decision 表：
   - id, review_id FK, target_kind, target_id, target_version,
     ai_verdict, ai_confidence, ai_reason, modification_hint, deprecate_reason,
     human_verdict, human_user_id FK, human_reason,
     final_verdict, decided_at, conflict_marker, accepted_low_confidence
   - 索引 ix_review_decision_review_id, ix_review_decision_target

3. review_lock 表：
   - id, review_id FK, target_kind, target_id, locked_at, expires_at
   - 索引 ix_review_lock_target, ix_review_lock_expires

Revision ID: add_review_tables
Revises: add_pipeline_tables
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_review_tables'
down_revision = 'add_pipeline_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'iteration_review',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('iteration_id', sa.Integer(), sa.ForeignKey('iterations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False, comment='评审类型：forward/backward/merged'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft', comment='评审状态：draft/in_progress/finalized/cancelled'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('finalized_at', sa.DateTime(), nullable=True),
        sa.Column('finalized_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_iteration_review_iteration_id', 'iteration_review', ['iteration_id'])
    op.create_index('ix_iteration_review_status', 'iteration_review', ['status'])

    op.create_table(
        'review_decision',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('iteration_review.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_kind', sa.String(20), nullable=False, comment='目标类型：case/testpoint/capability'),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('target_version', sa.Integer(), nullable=True),
        sa.Column('ai_verdict', sa.String(50), nullable=True, comment='AI 判定：keep/modify/deprecate'),
        sa.Column('ai_confidence', sa.Integer(), nullable=True, comment='AI 置信度 0-100'),
        sa.Column('ai_reason', sa.Text(), nullable=True),
        sa.Column('modification_hint', sa.Text(), nullable=True),
        sa.Column('deprecate_reason', sa.Text(), nullable=True),
        sa.Column('human_verdict', sa.String(50), nullable=True, comment='人工判定：keep/modify/deprecate'),
        sa.Column('human_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('human_reason', sa.Text(), nullable=True),
        sa.Column('final_verdict', sa.String(50), nullable=False, comment='最终判定'),
        sa.Column('decided_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('conflict_marker', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('accepted_low_confidence', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_decision_review_id', 'review_decision', ['review_id'])
    op.create_index('ix_review_decision_target', 'review_decision', ['target_kind', 'target_id'])

    op.create_table(
        'review_lock',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('iteration_review.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_kind', sa.String(20), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('locked_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_lock_target', 'review_lock', ['target_kind', 'target_id'])
    op.create_index('ix_review_lock_expires', 'review_lock', ['expires_at'])


def downgrade() -> None:
    op.drop_table('review_lock')
    op.drop_table('review_decision')
    op.drop_table('iteration_review')
