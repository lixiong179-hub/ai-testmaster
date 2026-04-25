"""
将 iteration_id 哨兵值 -1 替换为 NULL

原设计：前端发送 iteration_id=0 表示"未分类"，后端转为 -1 存储。
新设计：使用 NULL 表示"未关联迭代"，符合数据库规范化原则。

本次迁移：
1. 将 project_files 表中 iteration_id=-1 的记录更新为 NULL
2. 将 ui_prototype_projects 表中 iteration_id=-1 的记录更新为 NULL

Revision ID: 20260424_remove_iteration_id_sentinel
Revises: 20260423_merge_heads
Create Date: 2026-04-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260424_remove_iteration_id_sentinel"
down_revision = "20260423_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    """
    将 iteration_id=-1 的哨兵值替换为 NULL。

    在事务中完成，确保数据一致性。同时清理其他可能的非法值（<=0）。
    """
    # 使用 connection 执行原生 SQL，在事务中完成
    connection = op.get_bind()

    # 清理 project_files 表：将 iteration_id<=0 的记录统一设为 NULL
    connection.execute(
        sa.text(
            "UPDATE project_files SET iteration_id = NULL "
            "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
        )
    )

    # 清理 ui_prototype_projects 表：将 iteration_id<=0 的记录统一设为 NULL
    connection.execute(
        sa.text(
            "UPDATE ui_prototype_projects SET iteration_id = NULL "
            "WHERE iteration_id IS NOT NULL AND iteration_id <= 0"
        )
    )


def downgrade():
    """
    回滚：将 iteration_id=NULL 的记录恢复为 -1。

    注意：回滚操作无法区分哪些 NULL 是原本就是 NULL 的记录，
    哪些是从 -1 迁移过来的。此回滚会将所有 iteration_id=NULL
    的记录都设为 -1，可能影响原本就是 NULL 的记录。
    请谨慎使用回滚操作。
    """
    connection = op.get_bind()

    # 回滚 project_files 表：将 iteration_id=NULL 的记录设为 -1
    connection.execute(
        sa.text(
            "UPDATE project_files SET iteration_id = -1 "
            "WHERE iteration_id IS NULL"
        )
    )

    # 回滚 ui_prototype_projects 表：将 iteration_id=NULL 的记录设为 -1
    connection.execute(
        sa.text(
            "UPDATE ui_prototype_projects SET iteration_id = -1 "
            "WHERE iteration_id IS NULL"
        )
    )
