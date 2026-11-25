"""移除废弃模型表及修复外键

- DROP TABLE: operation_logs, nl_test_steps, test_case_data, api_cost_logs,
  code_reviews, review_items, review_comments, review_metrics,
  groups, user_group, group_role, resource_permissions
- ALTER: test_cases.last_review_id 外键从 code_reviews.id 改为 iteration_reviews.id
"""
from alembic import op
import sqlalchemy as sa

revision = "20260612_remove_deprecated_models"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 修复 test_cases.last_review_id 外键
    op.drop_constraint("test_cases_last_review_id_fkey", "test_cases", type_="foreignkey")
    op.create_foreign_key(
        "test_cases_last_review_id_fkey",
        "test_cases", "iteration_review",
        ["last_review_id"], ["id"],
        ondelete="SET NULL",
    )

    # 2. 删除废弃表（先删有外键依赖的子表，再删主表）
    op.drop_table("review_metrics", if_exists=True)
    op.drop_table("review_comments", if_exists=True)
    op.drop_table("review_items", if_exists=True)
    op.drop_table("code_reviews", if_exists=True)
    op.drop_table("operation_logs", if_exists=True)
    op.drop_table("nl_test_steps", if_exists=True)
    op.drop_table("test_case_data", if_exists=True)
    op.drop_table("api_cost_logs", if_exists=True)
    op.drop_table("resource_permissions", if_exists=True)
    op.drop_table("group_role", if_exists=True)
    op.drop_table("user_group", if_exists=True)
    op.drop_table("groups", if_exists=True)
    op.drop_table("feature_flags", if_exists=True)

    # 3. 删除 A/B 测试指标表（模块已废弃：只写不读，无前端，无测试）
    op.drop_table("ab_test_metrics", if_exists=True)


def downgrade() -> None:
    # 注意: downgrade 仅恢复表结构，不恢复数据
    # 恢复外键
    op.drop_constraint("test_cases_last_review_id_fkey", "test_cases", type_="foreignkey")
    op.create_foreign_key(
        "test_cases_last_review_id_fkey",
        "test_cases", "code_reviews",
        ["last_review_id"], ["id"],
        ondelete="SET NULL",
    )

    # 恢复表（简化版，仅结构）
    op.create_table("groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), unique=True, nullable=False),
    )
    op.create_table("user_group",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table("group_role",
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table("resource_permissions",
        sa.Column("resource_id", sa.Integer(), primary_key=True),
        sa.Column("resource_type", sa.String(50), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table("api_cost_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(100)),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("total_cost", sa.Float()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table("test_case_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("test_case_id", sa.Integer(), sa.ForeignKey("test_cases.id", ondelete="CASCADE")),
        sa.Column("test_data_id", sa.Integer(), sa.ForeignKey("test_data.id", ondelete="CASCADE")),
    )
    op.create_table("nl_test_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("step_id", sa.Integer(), sa.ForeignKey("test_steps.id", ondelete="CASCADE")),
        sa.Column("raw_text", sa.Text()),
    )
    op.create_table("operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer()),
        sa.Column("action", sa.String(100)),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", sa.Integer()),
        sa.Column("detail", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table("code_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200)),
        sa.Column("repository", sa.String(500)),
        sa.Column("branch", sa.String(200)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table("review_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("code_reviews.id", ondelete="CASCADE")),
        sa.Column("file_path", sa.String(500)),
        sa.Column("line_start", sa.Integer()),
        sa.Column("line_end", sa.Integer()),
        sa.Column("issue_type", sa.String(50)),
        sa.Column("description", sa.Text()),
    )
    op.create_table("review_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("review_items.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("content", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_table("review_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("code_reviews.id", ondelete="CASCADE")),
        sa.Column("metric_name", sa.String(100)),
        sa.Column("metric_value", sa.String(200)),
    )
