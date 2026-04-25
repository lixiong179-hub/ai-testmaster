from typing import List, Optional
"""
用例质量检查端点模块

本模块定义用例质量检查的API端点，支持按规则对测试用例进行质量评分和问题检测。

路由前缀: /caseQuality（由父模块case_quality.py注册）
标签: 用例质量

端点概览:
    - POST /{test_case_id}/check     - 执行质量检查
    - GET  /{test_case_id}/check-result - 获取检查结果
    - POST /batch-check              - 批量质量检查

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 质量检查规则包括：步骤完整性、预期结果明确性、测试数据有效性等
    - 评分采用百分制，低于60分为不合格
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from loguru import logger

from app.db.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.services.case_quality import CaseQualityAnalyzer
from app.models.user import User

router = APIRouter()


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
    reports: List[QualityReportSchema] = []


class OptimizationSuggestionSchema(BaseModel):
    category: str
    title: str
    description: str
    priority: str
    impact: str


from enum import Enum


class CaseReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_OPTIMIZATION = "needs_optimization"


class CaseReviewRequest(BaseModel):
    status: str = Field(..., description="审核状态: pending/approved/rejected/needs_optimization")
    review_comment: Optional[str] = Field(None, description="审核意见")
    priority: Optional[str] = Field(None, description="优先级: high/medium/low")


class CaseReviewResponse(BaseModel):
    case_id: int
    status: str
    review_comment: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[str]
    priority: Optional[str]


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


@router.get("/cases/{case_id}/quality", response_model=QualityReportSchema)
async def analyze_case_quality(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analyzer = CaseQualityAnalyzer(db)

    try:
        report = await analyzer.analyze_case_quality(case_id)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"用例质量分析失败: {e}")
        raise HTTPException(status_code=500, detail="分析失败")


@router.get("/projects/{project_id}/quality", response_model=ProjectQualitySummarySchema)
async def analyze_project_quality(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analyzer = CaseQualityAnalyzer(db)

    try:
        summary = await analyzer.analyze_project_quality(project_id)
        return summary
    except Exception as e:
        logger.error(f"项目质量分析失败: {e}")
        raise HTTPException(status_code=500, detail="分析失败")


@router.get("/cases/{case_id}/quality/trend")
async def get_case_quality_trend(
    case_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.test_case import TestCase
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    analyzer = CaseQualityAnalyzer(db)

    try:
        trend = await analyzer.get_quality_trend(test_case.project_id, days)
        return {
            "case_id": case_id,
            "project_id": test_case.project_id,
            "days": days,
            "trend": trend
        }
    except Exception as e:
        logger.error(f"获取趋势失败: {e}")
        raise HTTPException(status_code=500, detail="获取趋势失败")


@router.post("/cases/{case_id}/optimize-locators")
async def optimize_case_locators(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.test_case import TestCase, TestStep
    from app.models.element_locator import ElementLocator

    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    steps = db.query(TestStep).filter(
        TestStep.test_case_id == case_id
    ).order_by(TestStep.step_number).all()

    analyzer = CaseQualityAnalyzer(db)
    coverage = analyzer._analyze_coverage(
        steps, project_id=test_case.project_id, test_case=test_case
    )

    steps_without_locator = []
    for step in steps:
        step_id = step.id if hasattr(step, 'id') else None
        if step_id:
            locator = db.query(ElementLocator).filter(
                ElementLocator.step_id == step_id
            ).first()
            if not locator:
                steps_without_locator.append({
                    "step_id": step_id,
                    "action": step.action if hasattr(step, 'action') else str(step),
                    "target_element": step.target_element if hasattr(step, 'target_element') else ""
                })

    return {
        "case_id": case_id,
        "current_coverage_rate": coverage.coverage_rate,
        "total_elements": coverage.total_elements,
        "covered_elements": coverage.covered_elements,
        "steps_without_locator": len(steps_without_locator),
        "steps_to_optimize": steps_without_locator,
        "potential_savings": len(steps_without_locator) * 0.8,
        "message": f"发现{len(steps_without_locator)}个步骤缺少元素定位，补充后可节省{len(steps_without_locator) * 0.8:.1f}单位成本"
    }


@router.post("/batch-analyze")
async def batch_analyze_cases(
    case_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analyzer = CaseQualityAnalyzer(db)

    results = []
    for case_id in case_ids:
        try:
            report = await analyzer.analyze_case_quality(case_id)
            results.append({
                "case_id": case_id,
                "case_name": report.case_name,
                "overall_score": report.overall_score,
                "status": "success"
            })
        except Exception as e:
            results.append({
                "case_id": case_id,
                "case_name": "",
                "overall_score": 0,
                "status": "failed",
                "error": str(e)
            })

    success_results = [r for r in results if r["status"] == "success"]
    avg_score = (
        sum(r["overall_score"] for r in success_results) / len(success_results)
        if success_results else 0
    )

    return {
        "total": len(case_ids),
        "success": len(success_results),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "average_score": round(avg_score, 1),
        "results": results
    }
