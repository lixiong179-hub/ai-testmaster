"""add self_healing_audits table

Revision ID: 20260724_add_self_healing_audits
Revises: 20260627_add_grounding_source_to_test_case
Create Date: 2026-07-24

新增 self_healing_audits 表，记录 UI 自动化执行过程中触发"自愈"的每一次
决策痕迹，支撑自愈体系增强（self-healing-enhancement Task 1）。

表结构要点：
    - id              : BigInteger 自增主键
    - test_case_id    : 触发自愈的用例 ID（外键关联 test_cases.id，单列索引）
    - step_index      : 触发自愈的步骤序号
    - locator_id      : 外键关联 element_locators.id（ondelete=SET NULL，
                        定位器删除时置 NULL 保留审计记录；单列索引）
    - old_selector    : 自愈前选择器
    - new_selector    : 自愈后选择器
    - failure_type    : 失败原因（element_gone/dom_changed/load_delay/env_noise）
    - strategy        : 自愈策略（mcp/vision/stagehand/rollback/retry/skip）
    - confidence      : 置信度（0.00-1.00，NULL 表示策略无需置信度）
    - token_cost      : LLM Token 消耗（非 AI 策略为 0）
    - low_confidence  : 是否低于置信度阈值（人工复核标记）
    - created_at      : 记录创建时间（UTC）

索引设计：
    - ix_self_healing_audits_test_case_id : 单列索引，按用例维度检索
    - ix_self_healing_audits_locator_id   : 单列索引，按定位器维度检索
    - idx_case_step                       : (test_case_id, step_index) 复合索引，
                                            覆盖按用例步骤维度检索的高频查询

外键约束：
    - fk_self_healing_audits_test_case_id : test_case_id → test_cases.id（默认 RESTRICT，
                                            保护审计记录，删除用例前需先清理审计记录）
    - fk_self_healing_audits_locator_id   : locator_id → element_locators.id，
                                            ondelete=SET NULL 保留审计记录

存量数据兼容：新表无存量数据，所有 NOT NULL 列均带 server_default，
            保证后续若有数据回填场景时迁移稳定。

回滚策略：先 drop_constraint 释放外键（MySQL 要求外键列索引随约束一起释放，
        否则 DROP INDEX 报 ER_CANT_DROP_FIELD_OR_KEY），再 drop_index 各索引，
        最后 drop_table，无数据损失风险（表为新增）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers used by Alembic.
revision: str = "20260724_add_self_healing_audits"
down_revision: Union[str, None] = "20260627_add_grounding_source_to_test_case"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 self_healing_audits 表并建立复合索引 idx_case_step。"""
    op.create_table(
        "self_healing_audits",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="自愈审计记录主键ID",
        ),
        sa.Column(
            "test_case_id",
            sa.Integer(),
            nullable=False,
            comment="触发自愈的测试用例ID",
        ),
        sa.Column(
            "step_index",
            sa.Integer(),
            nullable=False,
            comment="触发自愈的步骤序号（0-based）",
        ),
        sa.Column(
            "locator_id",
            sa.Integer(),
            nullable=True,
            comment="关联的元素定位器ID（外键关联 element_locators，定位器删除时置 NULL）",
        ),
        sa.Column(
            "old_selector",
            sa.String(length=512),
            nullable=True,
            comment="自愈前选择器（CSS/XPath 等）",
        ),
        sa.Column(
            "new_selector",
            sa.String(length=512),
            nullable=True,
            comment="自愈后选择器（CSS/XPath 等）",
        ),
        sa.Column(
            "failure_type",
            sa.String(length=32),
            nullable=False,
            comment="失败原因: element_gone/dom_changed/load_delay/env_noise",
        ),
        sa.Column(
            "strategy",
            sa.String(length=32),
            nullable=False,
            comment="自愈策略: mcp/vision/stagehand/rollback/retry/skip",
        ),
        sa.Column(
            "confidence",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="自愈决策置信度（0.00-1.00），NULL 表示策略无需置信度",
        ),
        sa.Column(
            "token_cost",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="本次自愈消耗的LLM Token数（非AI策略为0）",
        ),
        sa.Column(
            "low_confidence",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="是否低于置信度阈值（人工复核标记）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            comment="记录创建时间（UTC）",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_self_healing_audits")),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_cases.id"],
            name=op.f("fk_self_healing_audits_test_case_id"),
        ),
        sa.ForeignKeyConstraint(
            ["locator_id"],
            ["element_locators.id"],
            name=op.f("fk_self_healing_audits_locator_id"),
            ondelete="SET NULL",
        ),
    )
    # 单列索引：按用例维度检索自愈记录
    op.create_index(
        op.f("ix_self_healing_audits_test_case_id"),
        "self_healing_audits",
        ["test_case_id"],
        unique=False,
    )
    # 单列索引：按定位器维度检索自愈记录
    op.create_index(
        op.f("ix_self_healing_audits_locator_id"),
        "self_healing_audits",
        ["locator_id"],
        unique=False,
    )
    # 复合索引：覆盖按用例步骤维度检索的高频查询
    op.create_index(
        "idx_case_step",
        "self_healing_audits",
        ["test_case_id", "step_index"],
        unique=False,
    )


def downgrade() -> None:
    """回滚：先删除外键约束（MySQL 要求外键列索引随约束释放），再删除索引与表。"""
    op.drop_constraint(
        op.f("fk_self_healing_audits_locator_id"),
        "self_healing_audits",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_self_healing_audits_test_case_id"),
        "self_healing_audits",
        type_="foreignkey",
    )
    op.drop_index("idx_case_step", table_name="self_healing_audits")
    op.drop_index(
        op.f("ix_self_healing_audits_locator_id"),
        table_name="self_healing_audits",
    )
    op.drop_index(
        op.f("ix_self_healing_audits_test_case_id"),
        table_name="self_healing_audits",
    )
    op.drop_table("self_healing_audits")
