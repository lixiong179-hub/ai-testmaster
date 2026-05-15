from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from loguru import logger

from app.db.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()


class PosteriorResultResponse(BaseModel):
    project_id: int
    posterior_quality_score: float
    review_pass_rate: float
    execution_pass_rate: float
    modification_rate: float
    total_reviewed: int
    total_executed: int
    total_cases: int
    meets_min_executions: bool

    class Config:
        from_attributes = True


class PosteriorStatsResponse(BaseModel):
    project_id: int
    avg_posterior_score: Optional[float]
    max_posterior_score: Optional[float]
    min_posterior_score: Optional[float]
    total_cases: int
    scored_cases: int
    unscored_cases: int
    distribution: Dict[str, int]

    class Config:
        from_attributes = True


@router.post("/posterior/{project_id}", response_model=PosteriorResultResponse)
async def trigger_posterior_scoring(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.project import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    from app.services.posterior_quality_service import compute_and_persist_posterior
    try:
        result = compute_and_persist_posterior(db, project_id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("后验质量评分计算失败: project_id={}, error={}", project_id, e)
        raise HTTPException(status_code=500, detail="后验质量评分计算失败")

    return PosteriorResultResponse(
        project_id=result["project_id"],
        posterior_quality_score=result["posterior_quality_score"],
        review_pass_rate=result["review_pass_rate"],
        execution_pass_rate=result["execution_pass_rate"],
        modification_rate=result["modification_rate"],
        total_reviewed=result["total_reviewed"],
        total_executed=result["total_executed"],
        total_cases=result["total_cases"],
        meets_min_executions=result["meets_min_executions"],
    )


@router.get("/posterior/{project_id}/result", response_model=PosteriorStatsResponse)
async def get_posterior_result(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.project import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    from app.models.test_case import TestCase

    stats = (
        db.query(
            func.count(TestCase.id).label("total_cases"),
            func.sum(case(
                (TestCase.posterior_quality_score.isnot(None), 1),
                else_=0,
            )).label("scored_cases"),
            func.avg(TestCase.posterior_quality_score).label("avg_score"),
            func.max(TestCase.posterior_quality_score).label("max_score"),
            func.min(TestCase.posterior_quality_score).label("min_score"),
        )
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        )
        .first()
    )

    total_cases = stats.total_cases or 0
    scored_cases = stats.scored_cases or 0
    unscored_cases = total_cases - scored_cases

    distribution: Dict[str, int] = {
        "A_90_100": 0,
        "B_75_89": 0,
        "C_60_74": 0,
        "D_0_59": 0,
    }

    if scored_cases > 0:
        scored_rows = (
            db.query(TestCase.posterior_quality_score)
            .filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted == False,
                TestCase.posterior_quality_score.isnot(None),
            )
            .all()
        )
        for row in scored_rows:
            score = row.posterior_quality_score
            if score is None:
                continue
            if score >= 90:
                distribution["A_90_100"] += 1
            elif score >= 75:
                distribution["B_75_89"] += 1
            elif score >= 60:
                distribution["C_60_74"] += 1
            else:
                distribution["D_0_59"] += 1

    return PosteriorStatsResponse(
        project_id=project_id,
        avg_posterior_score=round(stats.avg_score, 2) if stats.avg_score else None,
        max_posterior_score=stats.max_score,
        min_posterior_score=stats.min_score,
        total_cases=total_cases,
        scored_cases=scored_cases,
        unscored_cases=unscored_cases,
        distribution=distribution,
    )
