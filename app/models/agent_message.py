"""
Agent 消息模型模块

本模块定义 AgentMessage 模型，记录 Agent 会话每轮对话的完整消息流，
包括 LLM 输出、工具调用参数与结果、Artifacts 引用、Token 消耗。

核心类概览：
    - AgentMessage : Agent 消息模型

表关系：
    - AgentSession → AgentMessage（一对多，session_id 关联，ondelete=CASCADE）

字段语义：
    - role            : 消息角色（system/user/assistant/tool）
    - content         : 消息内容（JSON，兼容文本/工具调用/多模态）
    - artifact_refs   : 引用的 Artifacts 列表（JSON 数组）
    - tool_call_id    : 工具调用 ID（仅 role=tool 时有值）
    - tool_name       : 工具名称（仅 assistant 触发工具调用时有值）
    - token_cost      : 本条消息消耗的 Token 数
"""
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.mysql import JSON

from app.db.database import Base
from app.utils.db_time import utcnow


# 消息角色枚举值常量
MESSAGE_ROLE_VALUES = ("system", "user", "assistant", "tool")


class AgentMessage(Base):
    """
    Agent 消息模型

    每条记录描述 Agent 会话的一轮消息：角色（system/user/assistant/tool）、
    消息内容（JSON 序列化，兼容文本/工具调用/多模态）、引用的 Artifacts、
    工具调用元信息与本条消息的 Token 消耗。

    表关系：
        - 外键关联 → AgentSession（session_id，ondelete=CASCADE，
                                       会话删除时消息级联清除）

    使用场景：
        - AgentRuntime 每轮迭代后追加 assistant 消息与 tool 消息
        - 构建 LLM 上下文时按 session_id + created_at 顺序读取历史
        - Agent API 端点查询会话消息流（支持分页）
    """
    __tablename__ = "agent_messages"
    __table_args__ = (
        # 复合索引：覆盖按会话+时间维度检索消息流的高频查询（LLM 上下文构建）
        Index("idx_session_created", "session_id", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="消息主键ID")
    session_id = Column(BigInteger, ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False, index=True, comment="会话ID")
    role = Column(String(32), nullable=False, comment="消息角色: system/user/assistant/tool")

    # JSON 内容：兼容纯文本、工具调用、多模态（图片/截图 URL）
    # 结构示例：
    #   - 文本: {"text": "..."}
    #   - 工具调用: {"text": null, "tool_calls": [{"id": "...", "name": "...", "arguments": {...}}]}
    #   - 工具结果: {"text": null, "tool_call_id": "...", "tool_result": {...}}
    content = Column(JSON, nullable=False, comment="消息内容（JSON，兼容文本/工具调用/多模态）")
    artifact_refs = Column(JSON, nullable=True, comment="引用的Artifacts列表（JSON数组）")

    tool_call_id = Column(String(128), nullable=True, comment="工具调用ID（仅role=tool时有值）")
    tool_name = Column(String(128), nullable=True, comment="工具名称（assistant触发工具调用时有值）")
    token_cost = Column(Integer, nullable=False, default=0, comment="本条消息Token消耗")

    created_at = Column(DateTime, default=utcnow, nullable=False, comment="消息创建时间（UTC）")

    def __repr__(self) -> str:
        return (
            f"<AgentMessage(id={self.id}, session_id={self.session_id}, "
            f"role={self.role}, tool={self.tool_name})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回消息核心字段字典，供 API 响应使用。"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "artifact_refs": self.artifact_refs,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "token_cost": self.token_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def validate_role(role: str) -> bool:
        """校验消息角色是否在允许枚举值内。"""
        return role in MESSAGE_ROLE_VALUES
