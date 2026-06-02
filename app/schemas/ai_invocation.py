"""
AI 调用审计查询 Schema 模块

本模块定义 AIInvocationGateway 审计增强相关的请求/响应 Schema：
    - AIInvocationStatsQuery: 成本聚合查询参数
    - AIInvocationStatsResponse: 成本聚合结果项
    - AIInvocationListQuery: 调用记录查询参数
    - AIInvocationListItem: 调用记录列表项
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class AIInvocationStatsQuery(BaseModel):
    """AI 调用成本聚合查询参数

    Attributes:
        project_id: 项目ID（必填）
        start_date: 起始日期（含），默认近30天
        end_date: 截止日期（含），默认今天
        group_by: 聚合维度：model/strategy/date
    """
    project_id: int = Field(..., gt=0, description="项目ID")
    start_date: Optional[date] = Field(None, description="起始日期（含）")
    end_date: Optional[date] = Field(None, description="截止日期（含）")
    group_by: str = Field("model", pattern="^(model|strategy|date)$", description="聚合维度")


class AIInvocationStatsResponse(BaseModel):
    """AI 调用成本聚合结果项

    Attributes:
        group_key: 聚合键值（模型名/策略名/日期字符串）
        total_calls: 总调用次数
        total_prompt_tokens: 总输入 Token 数
        total_completion_tokens: 总输出 Token 数
        total_cost_usd: 总成本（美元）
    """
    group_key: str
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float


class AIInvocationListQuery(BaseModel):
    """AI 调用记录查询参数

    Attributes:
        batch_id: 生成批次ID（可选）
        project_id: 项目ID（可选）
        page: 页码，从1开始
        page_size: 每页条数
    """
    batch_id: Optional[int] = Field(None, description="生成批次ID")
    project_id: Optional[int] = Field(None, gt=0, description="项目ID")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class AIInvocationListItem(BaseModel):
    """AI 调用记录列表项

    包含 AICallLog 全部字段（含审计增强字段），
    通过 generation_batch → project 间接关联项目。

    Attributes:
        id: 记录ID
        run_id: 关联运行ID
        step_name: Step 名称
        model: 使用的AI模型
        prompt_tokens: 输入Token数
        completion_tokens: 输出Token数
        cost_usd: 调用成本（美元）
        latency_ms: 调用耗时（毫秒）
        status: 状态
        error_message: 错误信息
        created_at: 创建时间
        generation_batch_id: 关联生成批次ID
        scenario_type: 资料组合场景
        generation_strategy: 生成策略
        prompt_key: Prompt模板键
        prompt_version: Prompt版本号
        prompt_hash: Prompt内容哈希
        error_code: 错误码枚举值
    """
    id: int
    run_id: Optional[int] = None
    step_name: Optional[str] = None
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    generation_batch_id: Optional[int] = None
    scenario_type: Optional[str] = None
    generation_strategy: Optional[str] = None
    prompt_key: Optional[str] = None
    prompt_version: Optional[int] = None
    prompt_hash: Optional[str] = None
    error_code: Optional[str] = None

    model_config = {"from_attributes": True}
