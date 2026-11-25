"""add case_refresh_suggestions table

Revision ID: 20260529_add_case_refresh_suggestions
Revises:
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = '20260529_add_case_refresh_suggestions'
down_revision = '20260527_merge_release_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'case_refresh_suggestions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.Integer(), nullable=True),
        sa.Column('trigger_reason', sa.String(length=100), nullable=False, comment='触发原因: stale/requirement_changed/ui_changed/manual'),
        sa.Column('triggered_at', sa.DateTime(), nullable=False, comment='触发时间'),
        sa.Column('suggestion_status', sa.String(length=30), nullable=False, server_default='pending', comment='建议状态: pending/accepted/rejected/applied/expired'),
        sa.Column('suggested_title', sa.String(length=255), nullable=True, comment='AI建议的用例标题'),
        sa.Column('suggested_steps', sa.JSON(), nullable=True, comment='AI建议的步骤JSON'),
        sa.Column('suggested_expected_result', sa.Text(), nullable=True, comment='AI建议的预期结果'),
        sa.Column('diff_description', sa.Text(), nullable=True, comment='差异说明'),
        sa.Column('deprecation_reason', sa.Text(), nullable=True, comment='建议废弃原因'),
        sa.Column('review_status', sa.String(length=30), nullable=False, server_default='pending', comment='人工确认状态: pending/approved/rejected'),
        sa.Column('reviewer_id', sa.Integer(), nullable=True, comment='确认人ID'),
        sa.Column('reviewer_name', sa.String(length=100), nullable=True, comment='确认人姓名'),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True, comment='确认时间'),
        sa.Column('reject_reason', sa.Text(), nullable=True, comment='驳回原因'),
        sa.Column('failure_reason', sa.Text(), nullable=True, comment='AI生成失败原因'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0', comment='重试次数'),
        sa.Column('model_version', sa.String(length=64), nullable=True, comment='生成建议的AI模型版本'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['test_cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requirement_id'], ['requirements.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_case_refresh_suggestions_id'), 'case_refresh_suggestions', ['id'])
    op.create_index(op.f('ix_case_refresh_suggestions_case_id'), 'case_refresh_suggestions', ['case_id'])
    op.create_index(op.f('ix_case_refresh_suggestions_requirement_id'), 'case_refresh_suggestions', ['requirement_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_case_refresh_suggestions_requirement_id'), table_name='case_refresh_suggestions')
    op.drop_index(op.f('ix_case_refresh_suggestions_case_id'), table_name='case_refresh_suggestions')
    op.drop_index(op.f('ix_case_refresh_suggestions_id'), table_name='case_refresh_suggestions')
    op.drop_table('case_refresh_suggestions')
