"""
Agent 会话模型模块

本模块定义 AgentSession 模型，记录每次 Agent 执行的会话级元数据，
是 Agent 架构 Phase 1 的核心数据载体，支撑会话历史、Token 治理、
循环检测、熔断与 Prometheus 指标导出。

核心类概览：
    - AgentSession : Agent 会话模型

表关系：
    - User → AgentSession（一对多，created_by 关联 users.id）
    - Project → AgentSession（一对多，project_id 关联 projects.id）
    - AgentSession → AgentMessage（一对多，session_id 关联）
    - AgentSession → AgentAudit（一对多，session_id 关联）

字段语义：
    - agent_type      : Agent 类型标识（test_generation/failure_analysis/...）
    - status          : 会话状态（running/completed/failed/cancelled/loop_detected/circuit_open）
    - token_cost      : 累计 Token 消耗（含 LLM + 工具调用）
    - iteration_count : 已执行迭代轮数
    - loop_detected   : 是否触发循环检测熔断
"""
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)

from app.db.database import Base
from app.utils.db_time import utcnow


# Agent 类型与状态枚举值常量，集中维护便于校验与文档对齐
AGENT_TYPE_VALUES = (
    "test_generation",
    "failure_analysis",
    "visual_validation",
    "locator_healing",
)
AGENT_STATUS_VALUES = (
    "running",
    "completed",
    "failed",
    "cancelled",
    "loop_detected",
    "circuit_open",
    "token_exhausted",
)


class AgentSession(Base):
    """
    Agent 会话模型

    每条记录描述一次 Agent 执行的会话级状态：哪个项目的哪种 Agent、由谁触发、
    当前状态、累计 Token 消耗与迭代次数，以及是否触发循环检测熔断。

    表关系：
        - 外键关联 → Project（project_id，ondelete=CASCADE）
        - 外键关联 → User（created_by，ondelete=SET NULL）
        - 一对多 → AgentMessage（通过 session_id 关联）
        - 一对多 → AgentAudit（通过 session_id 关联）

    使用场景：
        - AgentRuntime.run() 创建会话、迭代中更新、完成时关闭
        - Agent API 端点查询会话历史与状态
        - Prometheus 指标按 agent_type/status 标签聚合
    """
    __tablename__ = "agent_sessions"
    __table_args__ = (
        # 复合索引：覆盖按项目+Agent 类型维度检索的高频查询
        Index("idx_project_agent", "project_id", "agent_type"),
        # 复合索引：覆盖按状态+开始时间维度检索运行中会话的高频查询
        Index("idx_status_started", "status", "started_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="Agent会话主键ID")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    agent_type = Column(String(64), nullable=False, comment="Agent类型: test_generation/failure_analysis/visual_validation/locator_healing")
    status = Column(String(32), nullable=False, default="running", comment="会话状态: running/completed/failed/cancelled/loop_detected/circuit_open/token_exhausted")

    started_at = Column(DateTime, default=utcnow, nullable=False, comment="会话开始时间（UTC）")
    completed_at = Column(DateTime, nullable=True, comment="会话完成时间（UTC，含 failed/cancelled）")

    token_cost = Column(Integer, nullable=False, default=0, comment="累计Token消耗")
    iteration_count = Column(Integer, nullable=False, default=0, comment="已执行迭代轮数")
    loop_detected = Column(Boolean, nullable=False, default=False, comment="是否触发循环检测熔断")

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="创建者用户ID")
    created_at = Column(DateTime, default=utcnow, nullable=False, comment="记录创建时间（UTC）")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False, comment="记录更新时间（UTC）")

    def __repr__(self) -> str:
        return (
            f"<AgentSession(id={self.id}, agent_type={self.agent_type}, "
            f"status={self.status}, iterations={self.iteration_count})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回会话核心字段字典，供 API 响应与日志输出使用。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_type": self.agent_type,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "token_cost": self.token_cost,
            "iteration_count": self.iteration_count,
            "loop_detected": self.loop_detected,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def validate_agent_type(agent_type: str) -> bool:
        """校验 Agent 类型是否在允许枚举值内。"""
        return agent_type in AGENT_TYPE_VALUES

    @staticmethod
    def validate_status(status: str) -> bool:
        """校验会话状态是否在允许枚举值内。"""
        return status in AGENT_STATUS_VALUES
