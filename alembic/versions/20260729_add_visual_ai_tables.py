"""add visual_baselines / visual_diffs / baseline_approvals tables

Revision ID: 20260729_add_visual_ai_tables
Revises: 20260729_add_test_coverage_map
Create Date: 2026-07-29

新增 Visual AI 引擎三张表，支撑视觉回归测试的基线管理、差异对比与
Diff 协作审批工作流（add-visual-ai-engine Task 1）。

表结构要点：

visual_baselines:
    - id               : BigInteger 自增主键
    - project_id       : 项目 ID（外键关联 projects.id，ondelete=CASCADE）
    - test_case_id     : 关联测试用例 ID（可空，支持页面级基线）
    - name             : 基线名称
    - page_url         : 被测页面 URL
    - viewport_width   : 视口宽度
    - viewport_height  : 视口高度
    - image_key        : 基线截图在 StorageBackend 中的对象 key
    - image_width      : 截图宽度
    - image_height     : 截图高度
    - match_level      : 对比模式（strict/layout/ignore_colors）
    - dom_snapshot_key : DOM 快照存储 key（Layout Match Level 使用）
    - status           : 基线状态（active/archived/superseded）
    - version          : 基线版本号
    - created_by       : 创建者用户 ID
    - created_at / updated_at

visual_diffs:
    - id                : BigInteger 自增主键
    - project_id        : 项目 ID
    - baseline_id       : 对比的基线 ID（外键关联 visual_baselines.id）
    - test_case_id      : 关联测试用例 ID（可空）
    - test_result_id    : 关联测试结果 ID（可空）
    - current_image_key : 当前截图存储 key
    - diff_image_key    : 差异图存储 key
    - diff_percentage   : 差异百分比（0.0-100.0）
    - diff_pixel_count  : 差异像素数
    - total_pixel_count : 总像素数
    - match_level       : 使用的对比模式
    - status            : 审批状态（pending/approved/rejected/auto_approved）
    - llm_analysis      : LLM 语义分析结果（JSON）
    - llm_token_cost    : LLM Token 消耗
    - created_at / updated_at

baseline_approvals:
    - id          : BigInteger 自增主键
    - project_id  : 项目 ID
    - diff_id     : 关联的 Diff ID（外键关联 visual_diffs.id）
    - baseline_id : 关联的基线 ID
    - action      : 审批动作（approve/reject/update_baseline）
    - comment     : 审批意见
    - reviewer_id : 审批人用户 ID
    - reviewed_at : 审批时间
    - created_at

索引设计：
    visual_baselines:
        - idx_baseline_project_page (project_id, page_url, viewport_width, viewport_height)
        - idx_baseline_project_status (project_id, status)
        - idx_baseline_test_case (test_case_id)

    visual_diffs:
        - idx_diff_project_status (project_id, status)
        - idx_diff_baseline (baseline_id)
        - idx_diff_case_result (test_case_id, test_result_id)

    baseline_approvals:
        - idx_approval_project_time (project_id, reviewed_at)
        - idx_approval_diff (diff_id)
        - idx_approval_baseline (baseline_id)

回滚策略：按反向顺序 drop_table（baseline_approvals → visual_diffs → visual_baselines），
        先 drop 子表释放外键依赖，再 drop 父表，无数据损失风险（表为新增）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers used by Alembic.
revision: str = "20260729_add_visual_ai_tables"
down_revision: Union[str, None] = "20260729_add_test_coverage_map"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 visual_baselines / visual_diffs / baseline_approvals 三张表。"""
    # 1. visual_baselines（基线表，无外键依赖其他新表，先创建）
    op.create_table(
        "visual_baselines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False, comment="基线名称"),
        sa.Column("page_url", sa.String(length=1024), nullable=False, comment="被测页面URL"),
        sa.Column("viewport_width", sa.Integer(), nullable=False, comment="视口宽度"),
        sa.Column("viewport_height", sa.Integer(), nullable=False, comment="视口高度"),
        sa.Column("image_key", sa.String(length=512), nullable=False, comment="基线截图存储key"),
        sa.Column("image_width", sa.Integer(), nullable=False, server_default="0", comment="截图宽度"),
        sa.Column("image_height", sa.Integer(), nullable=False, server_default="0", comment="截图高度"),
        sa.Column("match_level", sa.String(length=32), nullable=False, server_default="strict", comment="对比模式"),
        sa.Column("dom_snapshot_key", sa.String(length=512), nullable=True, comment="DOM快照存储key"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active", comment="基线状态"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1", comment="基线版本号"),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="创建者用户ID"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_baseline_project_page", "visual_baselines", ["project_id", "page_url", "viewport_width", "viewport_height"])
    op.create_index("idx_baseline_project_status", "visual_baselines", ["project_id", "status"])
    op.create_index("idx_baseline_test_case", "visual_baselines", ["test_case_id"])

    # 2. visual_diffs（差异表，外键依赖 visual_baselines）
    op.create_table(
        "visual_diffs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("baseline_id", sa.BigInteger(), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=True),
        sa.Column("test_result_id", sa.Integer(), nullable=True),
        sa.Column("current_image_key", sa.String(length=512), nullable=False, comment="当前截图存储key"),
        sa.Column("diff_image_key", sa.String(length=512), nullable=True, comment="差异图存储key"),
        sa.Column("diff_percentage", sa.Float(), nullable=False, server_default="0.0", comment="差异百分比"),
        sa.Column("diff_pixel_count", sa.Integer(), nullable=False, server_default="0", comment="差异像素数"),
        sa.Column("total_pixel_count", sa.Integer(), nullable=False, server_default="0", comment="总像素数"),
        sa.Column("match_level", sa.String(length=32), nullable=False, server_default="strict", comment="对比模式"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending", comment="审批状态"),
        sa.Column("llm_analysis", sa.Text(), nullable=True, comment="LLM语义分析结果"),
        sa.Column("llm_token_cost", sa.Integer(), nullable=False, server_default="0", comment="LLM Token消耗"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_id"], ["visual_baselines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["test_result_id"], ["test_results.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_diff_project_status", "visual_diffs", ["project_id", "status"])
    op.create_index("idx_diff_baseline", "visual_diffs", ["baseline_id"])
    op.create_index("idx_diff_case_result", "visual_diffs", ["test_case_id", "test_result_id"])

    # 3. baseline_approvals（审批表，外键依赖 visual_diffs 和 visual_baselines）
    op.create_table(
        "baseline_approvals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("diff_id", sa.BigInteger(), nullable=False),
        sa.Column("baseline_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False, comment="审批动作"),
        sa.Column("comment", sa.Text(), nullable=True, comment="审批意见"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True, comment="审批人用户ID"),
        sa.Column("reviewed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="审批时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False, comment="创建时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diff_id"], ["visual_diffs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_id"], ["visual_baselines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_approval_project_time", "baseline_approvals", ["project_id", "reviewed_at"])
    op.create_index("idx_approval_diff", "baseline_approvals", ["diff_id"])
    op.create_index("idx_approval_baseline", "baseline_approvals", ["baseline_id"])


def downgrade() -> None:
    """回滚：按反向顺序删除三张表。"""
    op.drop_index("idx_approval_baseline", table_name="baseline_approvals")
    op.drop_index("idx_approval_diff", table_name="baseline_approvals")
    op.drop_index("idx_approval_project_time", table_name="baseline_approvals")
    op.drop_table("baseline_approvals")

    op.drop_index("idx_diff_case_result", table_name="visual_diffs")
    op.drop_index("idx_diff_baseline", table_name="visual_diffs")
    op.drop_index("idx_diff_project_status", table_name="visual_diffs")
    op.drop_table("visual_diffs")

    op.drop_index("idx_baseline_test_case", table_name="visual_baselines")
    op.drop_index("idx_baseline_project_status", table_name="visual_baselines")
    op.drop_index("idx_baseline_project_page", table_name="visual_baselines")
    op.drop_table("visual_baselines")
