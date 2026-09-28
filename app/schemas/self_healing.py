"""
自愈模块 Pydantic Schema 定义。

包含自愈审计记录、回滚响应、项目级配置的请求/响应模型，
供自愈相关端点与 service 层使用。

响应信封统一使用 app.schemas.common.ApiResponse[T] 泛型封装，例如：
    - ApiResponse[AuditListResponse]   审计分页列表
    - ApiResponse[RollbackResponse]    回滚结果
    - ApiResponse[SelfHealingConfigResponse]  配置读取/更新
"""
from datetime import datetime

from pydantic import BaseModel, Field


class AuditResponse(BaseModel):
    """自愈审计记录响应模型，对应 SelfHealingAudit 表。"""

    id: int
    test_case_id: int
    step_index: int
    locator_id: int | None = None
    old_selector: str | None = None
    new_selector: str | None = None
    failure_type: str
    strategy: str
    confidence: float | None = None
    token_cost: int = 0
    low_confidence: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    """自愈审计分页列表响应。"""

    items: list[AuditResponse]
    total: int
    page: int
    page_size: int


class RollbackResponse(BaseModel):
    """自愈回滚操作响应。

    rollback 后会恢复旧 selector 并生成一条新审计记录，
    new_audit_id 指向该回滚审计。
    """

    audit_id: int
    restored_selector: str
    new_audit_id: int
    message: str


class SelfHealingConfigResponse(BaseModel):
    """项目级自愈配置响应。

    enabled 已合并全局开关（全局关则必为 False）。
    """

    enabled: bool
    strategies: list[str]
    token_limit: int


class SelfHealingConfigUpdate(BaseModel):
    """项目级自愈配置更新请求。

    所有字段可选，仅更新传入字段。token_limit 取值范围 [1, 10000]；
    strategies 必须为 ["mcp","vision","stagehand"] 子集（service 层强校验）。
    """

    enabled: bool | None = None
    strategies: list[str] | None = None
    token_limit: int | None = Field(None, ge=1, le=10000)
