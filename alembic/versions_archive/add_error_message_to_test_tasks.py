"""为 test_tasks 表增加 error_message 列

业务背景（P1 E-08：超时任务自动停止）：
    超时监控器在任务超过 TASK_TIMEOUT_SECONDS 后将其标记为 FAILED，
    需要一个任务级字段记录"超时/失败原因"，供前端展示与排障使用。
    历史上失败原因仅存在于 TestResult.error_msg（用例级），
    缺少任务级聚合字段，无法表达"整个任务因超时而失败"。

变更内容：
    - 新增 test_tasks.error_message TEXT NULL，comment='任务级失败/超时原因'

回滚：
    - 删除 error_message 列

Revision ID: add_err_msg_test_tasks
Revises: add_ai_call_log
Create Date: 2026-09-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_err_msg_test_tasks'
down_revision = 'add_ai_call_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：为 test_tasks 增加 error_message 列。

    使用 IF NOT EXISTS 语义由 Alembic 的 batch_alter_table 在 MySQL 上
    通过 inspect 判定是否已存在列，避免重复执行报错（测试库可能已 create_all
    含此列，生产库走迁移）。
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('test_tasks')}
    if 'error_message' not in existing_columns:
        with op.batch_alter_table('test_tasks') as batch_op:
            batch_op.add_column(
                sa.Column('error_message', sa.Text(), nullable=True, comment='任务级失败/超时原因')
            )


def downgrade() -> None:
    """回滚：删除 test_tasks.error_message 列。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('test_tasks')}
    if 'error_message' in existing_columns:
        with op.batch_alter_table('test_tasks') as batch_op:
            batch_op.drop_column('error_message')
