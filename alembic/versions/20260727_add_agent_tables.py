"""add agent_sessions / agent_messages / agent_audits tables

Revision ID: 20260727_add_agent_tables
Revises: 20260724_add_self_healing_audits
Create Date: 2026-07-27

新增 Agent 架构 Phase 1 三张表，支撑共享 Agent 框架的会话历史、
消息流、审计与 HITL 审批能力（add-agent-architecture Task 1）。

表结构要点：

agent_sessions:
    - id              : BigInteger 自增主键
    - project_id      : 项目 ID（外键关联 projects.id，ondelete=CASCADE）
    - agent_type      : Agent 类型（test_generation/failure_analysis/...）
    - status          : 会话状态（running/completed/failed/cancelled/loop_detected/circuit_open/token_exhausted）
    - started_at      : 会话开始时间
    - completed_at    : 会话完成时间（含 failed/cancelled）
    - token_cost      : 累计 Token 消耗
    - iteration_count : 已执行迭代轮数
    - loop_detected   : 是否触发循环检测熔断
    - created_by      : 创建者用户 ID（外键关联 users.id，ondelete=SET NULL）
    - created_at / updated_at

agent_messages:
    - id              : BigInteger 自增主键
    - session_id      : 会话 ID（外键关联 agent_sessions.id，ondelete=CASCADE）
    - role            : 消息角色（system/user/assistant/tool）
    - content         : 消息内容（JSON，兼容文本/工具调用/多模态）
    - artifact_refs   : 引用的 Artifacts 列表（JSON 数组）
    - tool_call_id    : 工具调用 ID（仅 role=tool 时有值）
    - tool_name       : 工具名称（assistant 触发工具调用时有值）
    - token_cost      : 本条消息 Token 消耗
    - created_at      : 消息创建时间

agent_audits:
    - id                  : BigInteger 自增主键
    - session_id          : 会话 ID（外键关联 agent_sessions.id，ondelete=CASCADE）
    - iteration           : 触发审计的迭代轮次
    - action_type         : 动作类型（tool_call/create_test_case/update_locator/rollback_*）
    - action_detail       : 动作详情（JSON，含工具名/参数/结果/资源 ID）
    - decision_confidence : 决策置信度（0.00-1.00，NULL 表示无需置信度）
    - human_approved      : 审批状态（0=待审批, 1=已批准, 2=已拒绝）
    - approved_by         : 审批人用户 ID（外键关联 users.id，ondelete=SET NULL）
    - approved_at         : 审批时间
    - created_at          : 审计记录创建时间

索引设计：
    - ix_agent_sessions_project_id         : 单列索引，按项目维度检索会话
    - ix_agent_sessions_created_by         : 单列索引，按创建者维度检索会话
    - idx_project_agent (project_id, agent_type) : 复合索引，按项目+Agent 类型检索
    - idx_status_started (status, started_at)    : 复合索引，按状态+开始时间检索运行中会话

    - ix_agent_messages_session_id         : 单列索引，按会话维度检索消息
    - idx_session_created (session_id, created_at) : 复合索引，按会话+时间检索消息流（LLM 上下文构建）

    - ix_agent_audits_session_id           : 单列索引，按会话维度检索审计
    - idx_session_iteration (session_id, iteration) : 复合索引，按会话+迭代检索审计
    - idx_pending_approval (human_approved, created_at) : 复合索引，按待审批+时间检索 HITL 队列

存量数据兼容：三张表均为新增，无存量数据，所有 NOT NULL 列均带 server_default，
            保证后续若有数据回填场景时迁移稳定。

回滚策略：先 drop_constraint 释放外键（MySQL 要求外键列索引随约束一起释放），
        再 drop_index 各索引，最后 drop_table，无数据损失风险（表为新增）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers used by Alembic.
revision: str = "20260727_add_agent_tables"
down_revision: Union[str, None] = "20260724_add_self_healing_audits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 agent_sessions / agent_messages / agent_audits 三张表与索引。"""
    # ========== 1. agent_sessions ==========
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="Agent会话主键ID"),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="项目ID"),
        sa.Column("agent_type", sa.String(length=64), nullable=False, comment="Agent类型: test_generation/failure_analysis/visual_validation/locator_healing"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running", comment="会话状态: running/completed/failed/cancelled/loop_detected/circuit_open/token_exhausted"),
        sa.Column("started_at", sa.DateTime(), nullable=False, comment="会话开始时间（UTC）"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="会话完成时间（UTC，含 failed/cancelled）"),
        sa.Column("token_cost", sa.Integer(), nullable=False, server_default="0", comment="累计Token消耗"),
        sa.Column("iteration_count", sa.Integer(), nullable=False, server_default="0", comment="已执行迭代轮数"),
        sa.Column("loop_detected", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否触发循环检测熔断"),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="创建者用户ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="记录创建时间（UTC）"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="记录更新时间（UTC）"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_sessions")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_agent_sessions_project_id"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_agent_sessions_created_by"), ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_agent_sessions_project_id"), "agent_sessions", ["project_id"], unique=False)
    op.create_index(op.f("ix_agent_sessions_created_by"), "agent_sessions", ["created_by"], unique=False)
    op.create_index("idx_project_agent", "agent_sessions", ["project_id", "agent_type"], unique=False)
    op.create_index("idx_status_started", "agent_sessions", ["status", "started_at"], unique=False)

    # ========== 2. agent_messages ==========
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="消息主键ID"),
        sa.Column("session_id", sa.BigInteger(), nullable=False, comment="会话ID"),
        sa.Column("role", sa.String(length=32), nullable=False, comment="消息角色: system/user/assistant/tool"),
        sa.Column("content", mysql.JSON(), nullable=False, comment="消息内容（JSON，兼容文本/工具调用/多模态）"),
        sa.Column("artifact_refs", mysql.JSON(), nullable=True, comment="引用的Artifacts列表（JSON数组）"),
        sa.Column("tool_call_id", sa.String(length=128), nullable=True, comment="工具调用ID（仅role=tool时有值）"),
        sa.Column("tool_name", sa.String(length=128), nullable=True, comment="工具名称（assistant触发工具调用时有值）"),
        sa.Column("token_cost", sa.Integer(), nullable=False, server_default="0", comment="本条消息Token消耗"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="消息创建时间（UTC）"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_messages")),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name=op.f("fk_agent_messages_session_id"), ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_agent_messages_session_id"), "agent_messages", ["session_id"], unique=False)
    op.create_index("idx_session_created", "agent_messages", ["session_id", "created_at"], unique=False)

    # ========== 3. agent_audits ==========
    op.create_table(
        "agent_audits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="审计记录主键ID"),
        sa.Column("session_id", sa.BigInteger(), nullable=False, comment="会话ID"),
        sa.Column("iteration", sa.Integer(), nullable=False, comment="触发审计的迭代轮次"),
        sa.Column("action_type", sa.String(length=64), nullable=False, comment="动作类型: tool_call/create_test_case/update_locator/rollback_*"),
        sa.Column("action_detail", mysql.JSON(), nullable=False, comment="动作详情（JSON，含工具名/参数/结果/资源ID）"),
        sa.Column("decision_confidence", sa.Numeric(precision=5, scale=2), nullable=True, comment="决策置信度（0.00-1.00），NULL 表示无需置信度"),
        sa.Column("human_approved", sa.Integer(), nullable=False, server_default="0", comment="审批状态: 0=待审批, 1=已批准, 2=已拒绝"),
        sa.Column("approved_by", sa.Integer(), nullable=True, comment="审批人用户ID"),
        sa.Column("approved_at", sa.DateTime(), nullable=True, comment="审批时间（UTC）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="审计记录创建时间（UTC）"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_audits")),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], name=op.f("fk_agent_audits_session_id"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], name=op.f("fk_agent_audits_approved_by"), ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_agent_audits_session_id"), "agent_audits", ["session_id"], unique=False)
    op.create_index("idx_session_iteration", "agent_audits", ["session_id", "iteration"], unique=False)
    op.create_index("idx_pending_approval", "agent_audits", ["human_approved", "created_at"], unique=False)


def downgrade() -> None:
    """回滚：先删除外键约束（MySQL 要求外键列索引随约束释放），再删除索引与表。"""
    # ========== 3. agent_audits ==========
    op.drop_constraint(op.f("fk_agent_audits_approved_by"), "agent_audits", type_="foreignkey")
    op.drop_constraint(op.f("fk_agent_audits_session_id"), "agent_audits", type_="foreignkey")
    op.drop_index("idx_pending_approval", table_name="agent_audits")
    op.drop_index("idx_session_iteration", table_name="agent_audits")
    op.drop_index(op.f("ix_agent_audits_session_id"), table_name="agent_audits")
    op.drop_table("agent_audits")

    # ========== 2. agent_messages ==========
    op.drop_constraint(op.f("fk_agent_messages_session_id"), "agent_messages", type_="foreignkey")
    op.drop_index("idx_session_created", table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_session_id"), table_name="agent_messages")
    op.drop_table("agent_messages")

    # ========== 1. agent_sessions ==========
    op.drop_constraint(op.f("fk_agent_sessions_created_by"), "agent_sessions", type_="foreignkey")
    op.drop_constraint(op.f("fk_agent_sessions_project_id"), "agent_sessions", type_="foreignkey")
    op.drop_index("idx_status_started", table_name="agent_sessions")
    op.drop_index("idx_project_agent", table_name="agent_sessions")
    op.drop_index(op.f("ix_agent_sessions_created_by"), table_name="agent_sessions")
    op.drop_index(op.f("ix_agent_sessions_project_id"), table_name="agent_sessions")
    op.drop_table("agent_sessions")
