"""Agent API Pydantic Schema 定义。

包含 Agent 会话、消息、审计的请求/响应模型，供 /api/v1/agents 端点使用。
响应信封统一使用 app.schemas.common.ApiResponse[T] 泛型封装，例如：
    - ApiResponse[SessionResponse]        单会话响应
    - ApiResponse[SessionListResponse]    会话分页列表
    - ApiResponse[List[MessageResponse]]  消息流
    - ApiResponse[AuditResponse]          审计审批结果
    - ApiResponse[RollbackResponse]       回滚结果

所有模型 extra="forbid"，响应模型额外开启 from_attributes 以支持 ORM 直接转换。
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    """创建 Agent 会话请求。

    initial_artifacts 为 Runtime 触发时使用的初始 Artifacts 输入，由后续
    Runtime 触发端点消费；本端点仅创建会话记录，不处理 Artifacts。
    """

    model_config = ConfigDict(extra="forbid")

    agent_type: str = Field(..., description="Agent 类型，需在 AGENT_TYPE_VALUES 内")
    project_id: int = Field(..., description="项目 ID")
    initial_artifacts: List[dict] = Field(
        default_factory=list, description="初始 Artifacts 输入，Runtime 触发时消费"
    )


class SessionResponse(BaseModel):
    """Agent 会话响应模型，对应 AgentSession 表核心字段。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    project_id: int
    agent_type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    token_cost: int
    iteration_count: int
    loop_detected: bool
    created_by: Optional[int] = None


class SessionListResponse(BaseModel):
    """Agent 会话分页列表响应。"""

    model_config = ConfigDict(extra="forbid")

    items: List[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    """Agent 消息响应模型，对应 AgentMessage 表核心字段。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    session_id: int
    role: str
    content: dict
    artifact_refs: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    token_cost: int
    created_at: Optional[datetime] = None


class AuditResponse(BaseModel):
    """Agent 审计响应模型，对应 AgentAudit 表核心字段。

    decision_confidence 在库中为 Numeric(5,2)，Pydantic lax 模式将 Decimal 强转 float。
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    session_id: int
    iteration: int
    action_type: str
    action_detail: dict
    decision_confidence: Optional[float] = None
    human_approved: int
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AuditListResponse(BaseModel):
    """Agent 审计分页列表响应。"""

    model_config = ConfigDict(extra="forbid")

    items: List[AuditResponse]
    total: int


class ApprovalRequest(BaseModel):
    """HITL 审批请求。approved=True 批准，False 拒绝。"""

    model_config = ConfigDict(extra="forbid")

    approved: bool = Field(True, description="True=批准, False=拒绝")
    reason: Optional[str] = Field(None, description="审批备注")


class RollbackRequest(BaseModel):
    """审计回滚请求。reason 记录回滚原因，写入补偿审计的 action_detail。"""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field("", description="回滚原因")


class RollbackResponse(BaseModel):
    """审计回滚响应。

    回滚成功后写入新的补偿审计记录，new_audit_id 指向该记录；
    original_action_type 为被回滚动作的原 action_type。
    """

    model_config = ConfigDict(extra="forbid")

    audit_id: int
    original_action_type: str
    rolled_back: bool
    new_audit_id: int
