"""为 review_lock 表添加 (target_kind, target_id) 唯一约束

防止并发场景下同一目标被重复加锁，配合 with_for_update() 行级锁
实现原子化加锁操作。

Revision ID: 20260616_add_uq_review_lock_target
Revises: 20260612_remove_deprecated_models
Create Date: 2026-06-16 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260616_add_uq_review_lock_target"
down_revision = "20260612_remove_deprecated_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先清理可能存在的重复数据（保留每个 target_kind+target_id 中 id 最大的记录）
    op.execute(
        """
        DELETE rl FROM review_lock rl
        INNER JOIN (
            SELECT target_kind, target_id, MAX(id) AS max_id
            FROM review_lock
            GROUP BY target_kind, target_id
            HAVING COUNT(*) > 1
        ) dup ON rl.target_kind = dup.target_kind
              AND rl.target_id = dup.target_id
              AND rl.id < dup.max_id
        """
    )
    op.create_unique_constraint(
        "uq_review_lock_target",
        "review_lock",
        ["target_kind", "target_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_review_lock_target", "review_lock", type_="unique")
