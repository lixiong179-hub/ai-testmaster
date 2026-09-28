"""
Agent 审计模型模块

本模块定义 AgentAudit 模型，记录 Agent 每轮迭代的决策痕迹，支撑
HITL（Human-in-the-Loop）审批、回滚操作与事后回溯。

核心类概览：
    - AgentAudit : Agent 审计模型

表关系：
    - AgentSession → AgentAudit（一对多，session_id 关联，ondelete=CASCADE）
    - User → AgentAudit（一对多，approved_by 关联 users.id，ondelete=SET NULL）

字段语义：
    - iteration             : 触发审计的迭代轮次（与 AgentSession.iteration_count 对应）
    - action_type           : 动作类型（tool_call/create_test_case/update_locator/...）
    - action_detail         : 动作详情（JSON，含工具名/参数/结果/资源 ID）
    - decision_confidence   : 决策置信度（0.00-1.00），低置信度需人工审批
    - human_approved        : 是否已通过人工审批
    - approved_by           : 审批人用户ID（NULL 表示未审批）

审计设计要点：
    1. 表本身只追加（append-only），不提供更新接口（除 human_approved/approved_by 审批字段）；
    2. 通过 idx_pending_approval 索引快速检索待审批动作；
    3. 回滚操作写入新审计记录，action_type 标记为 rollback_<原action_type>，
       action_detail 中含原审计 ID 与回滚原因。
"""
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.mysql import JSON

from app.db.database import Base
from app.utils.db_time import utcnow


# 动作类型枚举值常量
ACTION_TYPE_VALUES = (
    "tool_call",
    "create_test_case",
    "update_locator",
    "create_test_step",
    "update_test_case",
    "rollback_create_test_case",
    "rollback_update_locator",
)


class AgentAudit(Base):
    """
    Agent 审计模型

    每条记录描述一次 Agent 决策痕迹：第几轮迭代、动作类型、动作详情、
    决策置信度，以及人工审批状态。低置信度动作需人工审批后才落库，
    审批后写入 human_approved=True + approved_by + approved_at。

    表关系：
        - 外键关联 → AgentSession（session_id，ondelete=CASCADE）
        - 外键关联 → User（approved_by，ondelete=SET NULL）

    使用场景：
        - AgentRuntime 每轮工具调用后写入审计
        - HITL 审批端点检索 pending 动作并标记审批结果
        - 回滚端点根据 action_type 调用对应回滚处理器
    """
    __tablename__ = "agent_audits"
    __table_args__ = (
        # 复合索引：覆盖按会话+迭代维度检索审计记录的高频查询
        Index("idx_session_iteration", "session_id", "iteration"),
        # 复合索引：覆盖按待审批+时间维度检索 HITL 队列的高频查询
        Index("idx_pending_approval", "human_approved", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="审计记录主键ID")
    session_id = Column(BigInteger, ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True, comment="会话ID")
    iteration = Column(Integer, nullable=False, comment="触发审计的迭代轮次")

    action_type = Column(String(64), nullable=False, comment="动作类型: tool_call/create_test_case/update_locator/rollback_*")
    # JSON 详情：含工具名/参数/结果/资源 ID 等动作上下文
    # 结构示例：
    #   - tool_call: {"tool_name": "create_test_case", "arguments": {...}, "result": {...}}
    #   - create_test_case: {"test_case_id": 123, "title": "...", "steps": [...]}
    #   - rollback_create_test_case: {"original_audit_id": 456, "reason": "...", "deleted_test_case_id": 123}
    action_detail = Column(JSON, nullable=False, comment="动作详情（JSON，含工具名/参数/结果/资源ID）")

    decision_confidence = Column(Numeric(5, 2), nullable=True, comment="决策置信度（0.00-1.00），NULL 表示无需置信度")

    human_approved = Column(Integer, nullable=False, default=0, comment="审批状态: 0=待审批, 1=已批准, 2=已拒绝")
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="审批人用户ID")
    approved_at = Column(DateTime, nullable=True, comment="审批时间（UTC）")

    created_at = Column(DateTime, default=utcnow, nullable=False, comment="审计记录创建时间（UTC）")

    def __repr__(self) -> str:
        return (
            f"<AgentAudit(id={self.id}, session_id={self.session_id}, "
            f"iter={self.iteration}, action={self.action_type})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回审计核心字段字典，供 API 响应使用。"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "iteration": self.iteration,
            "action_type": self.action_type,
            "action_detail": self.action_detail,
            "decision_confidence": float(self.decision_confidence) if self.decision_confidence is not None else None,
            "human_approved": self.human_approved,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def validate_action_type(action_type: str) -> bool:
        """校验动作类型是否在允许枚举值内。"""
        return action_type in ACTION_TYPE_VALUES

    @staticmethod
    def validate_confidence(confidence: Optional[float]) -> bool:
        """校验置信度取值范围是否合法（0.00-1.00）。"""
        if confidence is None:
            return True
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return False
        return 0.0 <= value <= 1.0
