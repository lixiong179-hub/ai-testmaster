"""add_history_asset_and_batch_history_field

Revision ID: 5ff2f5eaa8da
Revises: add_generation_batch
Create Date: 2026-06-01 18:00:33.477589

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5ff2f5eaa8da"
down_revision: Union[str, None] = "add_generation_batch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "history_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "asset_type",
            sa.String(length=30),
            nullable=False,
            comment="资产类型: excel/xmind/system_cases",
        ),
        sa.Column("file_path", sa.String(length=500), nullable=True, comment="上传文件路径"),
        sa.Column("original_filename", sa.String(length=255), nullable=True, comment="原始文件名"),
        sa.Column(
            "parse_status",
            sa.String(length=30),
            nullable=False,
            comment="解析状态: pending/parsing/completed/failed",
        ),
        sa.Column("parse_error", sa.String(length=500), nullable=True, comment="解析失败原因"),
        sa.Column(
            "parsed_cases_json", sa.JSON(), nullable=True, comment="解析后的结构化历史用例数据"
        ),
        sa.Column("case_count", sa.Integer(), nullable=False, comment="解析出的用例数量"),
        sa.Column("batch_id", sa.Integer(), nullable=True, comment="关联的生成批次ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["generation_batches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_history_asset_project_created",
        "history_assets",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_history_asset_project_type",
        "history_assets",
        ["project_id", "asset_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_history_assets_batch_id"), "history_assets", ["batch_id"], unique=False
    )
    op.create_index(op.f("ix_history_assets_id"), "history_assets", ["id"], unique=False)
    op.create_index(
        op.f("ix_history_assets_project_id"), "history_assets", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_history_assets_user_id"), "history_assets", ["user_id"], unique=False)
    op.add_column(
        "generation_batches",
        sa.Column(
            "history_asset_ids_json", sa.JSON(), nullable=False, comment="本次选择的历史资产ID列表"
        ),
    )


def downgrade() -> None:
    op.drop_column("generation_batches", "history_asset_ids_json")
    op.drop_index(op.f("ix_history_assets_user_id"), table_name="history_assets")
    op.drop_index(op.f("ix_history_assets_project_id"), table_name="history_assets")
    op.drop_index(op.f("ix_history_assets_id"), table_name="history_assets")
    op.drop_index(op.f("ix_history_assets_batch_id"), table_name="history_assets")
    op.drop_index("ix_history_asset_project_type", table_name="history_assets")
    op.drop_index("ix_history_asset_project_created", table_name="history_assets")
    op.drop_table("history_assets")
