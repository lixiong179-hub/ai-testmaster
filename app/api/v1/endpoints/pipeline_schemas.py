"""Pipeline 请求模型定义

集中定义 Pipeline 相关的 Pydantic 请求模型，供主模块和子模块共用。
"""

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    scenario: int = Field(1, ge=1, le=8, description="场景编号")
    ai_model: str | None = Field(None, description="指定 AI 模型（可选）")
    dry_run: bool = Field(False, description="试运行模式")


class PipelineResumeRequest(BaseModel):
    confirmation_payload: dict | None = Field(None, description="确认载荷")


class SupplementSignalsRequest(BaseModel):
    confirmed_capabilities: list[dict] = Field(default_factory=list, description="确认后的业务能力列表")
    answers: list[dict] = Field(default_factory=list, description="对 AI 疑问的回答")
    change_summary: dict | None = Field(None, description="变更摘要（旧项目模式）")
    notes: str | None = Field(None, description="补充说明")


class Scenario4PrecheckRequest(BaseModel):
    project_id: int = Field(..., ge=1, description="项目ID")
    ui_project_id: int | None = Field(None, description="UI原型项目ID")
    screen_ids: list[int] | None = Field(None, description="UI屏幕ID列表")
    iteration_id: int | None = Field(None, description="已有迭代ID（可选）")
    test_point_ids: list[int] | None = Field(None, description="测试点ID列表（可选）")
    requirement_file_ids: list[int] | None = Field(None, description="需求文件ID列表（可选）")
    change_source: str | None = Field(
        None,
        pattern="^(ui_flow|requirement|mixed)$",
        description="变化来源：ui_flow/requirement/mixed",
    )
