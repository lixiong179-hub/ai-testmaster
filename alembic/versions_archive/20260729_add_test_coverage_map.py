"""add test_coverage_maps table

Revision ID: 20260729_add_test_coverage_map
Revises: 20260728_add_project_members
Create Date: 2026-07-29

新增 test_coverage_maps 表，支撑 TIA（Test Impact Analysis）智能调度。
持久化"测试用例 ↔ 代码文件行范围"映射，供 TIA 启动时批量加载构造
CoverageEntry 列表，避免每次执行重新解析 coverage.json 的开销。

表结构要点：
    test_coverage_maps:
        - id          : BigInteger 自增主键
        - project_id  : 项目 ID（外键关联 projects.id，ondelete=CASCADE）
        - test_case_id: 测试用例 ID（外键关联 test_cases.id，ondelete=CASCADE）
        - file_path   : 相对项目根目录的代码文件路径
        - line_start  : 覆盖起始行号（1-based，包含）
        - line_end    : 覆盖结束行号（1-based，包含）
        - test_name   : 测试函数名（调试用，不参与业务）
        - created_at / updated_at

索引设计：
    - idx_coverage_case         (test_case_id)              : 按用例维度检索
    - idx_coverage_file         (file_path)                 : 按文件维度检索（TIA 主查询路径）
    - idx_coverage_project_file (project_id, file_path)     : 按项目批量加载（TIA 冷启动）
    - uq_case_file              (test_case_id, file_path) UNIQUE : 同用例+同文件仅一行（upsert 唯一键）

回滚策略：drop_table 即可，无数据损失（映射为新增数据，由测试执行后采集生成）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers used by Alembic.
revision: str = "20260729_add_test_coverage_map"
down_revision: Union[str, None] = "20260728_add_project_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 test_coverage_maps 表。"""
    op.create_table(
        "test_coverage_maps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="覆盖率映射主键ID"),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID（冗余存储，加速按项目过滤避免 JOIN）"),
        sa.Column("test_case_id", sa.Integer(), nullable=False, comment="测试用例ID"),
        sa.Column("file_path", sa.String(length=512), nullable=False, comment="相对项目根目录的代码文件路径，如 app/services/foo.py"),
        sa.Column("line_start", sa.Integer(), nullable=False, comment="覆盖起始行号（1-based，包含）"),
        sa.Column("line_end", sa.Integer(), nullable=False, comment="覆盖结束行号（1-based，包含）"),
        sa.Column("test_name", sa.String(length=256), nullable=False, server_default="", comment="测试函数名，仅用于调试与日志，不参与业务逻辑"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="记录创建时间（UTC）"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="记录更新时间（UTC）"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_coverage_maps")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_test_coverage_maps_project_id"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], name=op.f("fk_test_coverage_maps_test_case_id"), ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_test_coverage_maps_project_id"), "test_coverage_maps", ["project_id"], unique=False)
    op.create_index("idx_coverage_case", "test_coverage_maps", ["test_case_id"], unique=False)
    op.create_index("idx_coverage_file", "test_coverage_maps", ["file_path"], unique=False)
    op.create_index("idx_coverage_project_file", "test_coverage_maps", ["project_id", "file_path"], unique=False)
    op.create_index("uq_case_file", "test_coverage_maps", ["test_case_id", "file_path"], unique=True)


def downgrade() -> None:
    """回滚：删除 test_coverage_maps 表。"""
    op.drop_index("uq_case_file", table_name="test_coverage_maps")
    op.drop_index("idx_coverage_project_file", table_name="test_coverage_maps")
    op.drop_index("idx_coverage_file", table_name="test_coverage_maps")
    op.drop_index("idx_coverage_case", table_name="test_coverage_maps")
    op.drop_index(op.f("ix_test_coverage_maps_project_id"), table_name="test_coverage_maps")
    op.drop_table("test_coverage_maps")
