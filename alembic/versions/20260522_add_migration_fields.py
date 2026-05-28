import sqlalchemy as sa
from alembic import op


revision = "20260522_add_migration_fields"
down_revision = "20260519_add_source_to_bugs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column(
            "target_device",
            sa.String(20),
            nullable=True,
            comment="目标设备类型：tablet/phone/desktop/web，为空表示通用",
        ),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "migration_source_id",
            sa.Integer,
            nullable=True,
            comment="迁移来源用例ID，跨设备迁移时指向原设备用例",
        ),
    )
    op.create_foreign_key(
        "fk_test_cases_migration_source_id",
        "test_cases",
        "test_cases",
        ["migration_source_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "migration_type",
            sa.String(20),
            nullable=True,
            comment="迁移类型：cloned=直接克隆/adapted=AI改写/split=拆分迁移/new=新增/deprecated=废弃",
        ),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "migration_batch_id",
            sa.String(50),
            nullable=True,
            comment="迁移批次ID，同一次批量迁移产出的用例共享此ID，用于回退",
        ),
    )
    op.add_column(
        "iterations",
        sa.Column(
            "target_device",
            sa.String(20),
            nullable=True,
            comment="迭代目标设备：tablet/phone/desktop/web",
        ),
    )


def downgrade() -> None:
    op.drop_column("iterations", "target_device")
    op.drop_column("test_cases", "migration_batch_id")
    op.drop_column("test_cases", "migration_type")
    op.drop_constraint("fk_test_cases_migration_source_id", "test_cases", type_="foreignkey")
    op.drop_column("test_cases", "migration_source_id")
    op.drop_column("test_cases", "target_device")
