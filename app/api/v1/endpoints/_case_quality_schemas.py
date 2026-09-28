"""用例质量模块共享 Schema 定义。

从 case_quality_check.py 拆出，供 case_quality_check 与 case_quality_report 共用。
死代码清理：原 OptimizationSuggestionSchema / CaseReviewStatus / CaseReviewResponse
均无外部引用，未迁移至此处。
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class ComplexityScoreSchema(BaseModel):
    step_count: int
    action_variety: int
    precondition_count: int
    has_verification: bool
    has_captcha: bool
    score: float
    level: str

    class Config:
        from_attributes = True


class RedundancyScoreSchema(BaseModel):
    similar_case_count: int
    similar_cases: List[dict]
    duplicate_step_count: int
    score: float
    level: str

    class Config:
        from_attributes = True


class CoverageScoreSchema(BaseModel):
    total_elements: int
    covered_elements: int
    uncovered_elements: int
    coverage_rate: float
    score: float
    level: str
    requirement_coverage_rate: float = 0.0
    ui_element_coverage_rate: float = 0.0
    locator_coverage_rate: float = 0.0
    requirement_details: Optional[dict] = None
    ui_element_details: Optional[dict] = None
    locator_details: Optional[dict] = None

    class Config:
        from_attributes = True


class QualityReportSchema(BaseModel):
    case_id: int
    case_name: str
    overall_score: float
    overall_level: str
    complexity: Optional[ComplexityScoreSchema] = None
    redundancy: Optional[RedundancyScoreSchema] = None
    coverage: Optional[CoverageScoreSchema] = None
    suggestions: List[str]
    analyzed_at: str

    class Config:
        from_attributes = True


class ProjectQualitySummarySchema(BaseModel):
    project_id: int
    total_cases: int
    average_score: float
    project_requirement_coverage: float = 0.0
    project_requirement_details: Optional[dict] = None
    reports: List[QualityReportSchema] = Field(default_factory=list)


class CaseReviewRequest(BaseModel):
    status: str = Field(..., description="审核状态: pending/approved/rejected/needs_optimization")
    review_comment: Optional[str] = Field(None, description="审核意见")
    priority: Optional[str] = Field(None, description="优先级: high/medium/low")


class CaseEditRequest(BaseModel):
    title: Optional[str] = Field(None, description="用例标题")
    description: Optional[str] = Field(None, description="用例描述")
    preconditions: Optional[str] = Field(None, description="前置条件")
    expected_result: Optional[str] = Field(None, description="预期结果")
    priority: Optional[str] = Field(None, description="优先级")


class StepEditRequest(BaseModel):
    step_id: int
    action: Optional[str] = Field(None, description="操作")
    target: Optional[str] = Field(None, description="目标")
    value: Optional[str] = Field(None, description="值")
    expected_result: Optional[str] = Field(None, description="预期结果")


__all__ = [
    "ComplexityScoreSchema",
    "RedundancyScoreSchema",
    "CoverageScoreSchema",
    "QualityReportSchema",
    "ProjectQualitySummarySchema",
    "CaseReviewRequest",
    "CaseEditRequest",
    "StepEditRequest",
]
